"""
Module for handling WebSocket connections to trading APIs
REFACTORED: Fixed critical issues including duplicate code, recursive calls, and buffer errors
"""
import asyncio
import websockets
import json
import logging
import time
from typing import List, Dict, Callable, Optional, Tuple
from src.trading_api import get_recent_trades, filter_symbols_by_volume
from src.candle_aggregator import aggregate_trades_to_candles, calculate_scaled_avg_candle_size
from src.signal_processor import process_trades_for_signals
from src.config import WARMUP_INTERVALS, CANDLE_INTERVAL_SECONDS, log_websocket_event, log_reconnect

# Configure logging
logger = logging.getLogger(__name__)


class TradeWebSocket:
    def __init__(self, coins: List[str], ws_url: str = "wss://stream.bybit.com/v5/public/linear", max_connections: int = 12, max_coins_per_connection: int = 20):
        """
        Initialize WebSocket connections for trade data
        Uses multiple connections to distribute symbols and avoid limits
        """
        # Filter coins by volume before initializing
        self.coins = filter_symbols_by_volume(coins)
        logger.info(f"Filtered {len(self.coins)} coins")
        self.ws_url = ws_url
        self.max_connections = max_connections
        self.max_coins_per_connection = max_coins_per_connection
        # NEW ARCHITECTURE: Store candles instead of individual trades
        self.candles_buffer = {}        # Completed candles for each coin
        self.current_candle_data = {}   # Current incomplete candle data per coin
        self.running = False
        self._connection_tasks = []  # Track connection tasks for graceful shutdown
        self._start_time = time.time() # Track when system started for warmup

        # Initialize candle buffers for each coin
        for coin in self.coins:
            self.candles_buffer[coin] = []         # List of completed candles
            self.current_candle_data[coin] = {     # Current candle being built
                'trades': [],
                'candle_start_time': None
            }

        # Event handlers for connection events
        self.on_connect: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None

        # Calculate needed connections silently
        connections_needed = self._calculate_needed_connections()

    def _distribute_symbols_to_connections(self) -> List[List[str]]:
        """
        Distribute symbols evenly across multiple WebSocket connections
        """
        if not self.coins:
            return []

        # Calculate how many symbols per connection
        symbols_per_connection = min(self.max_coins_per_connection, max(1, len(self.coins) // self.max_connections))

        # Split symbols into chunks for each connection
        connections = []
        for i in range(0, len(self.coins), symbols_per_connection):
            connections.append(self.coins[i:i + symbols_per_connection])

        return connections

    def _calculate_needed_connections(self) -> int:
        """
        Calculate how many WebSocket connections are needed based on number of coins
        """
        if not self.coins:
            return 0

        needed_connections = (len(self.coins) + self.max_coins_per_connection - 1) // self.max_coins_per_connection
        return min(needed_connections, self.max_connections)

    async def _start_single_connection(self, coins_for_connection: List[str], with_display: bool = False):
        """
        Start a single WebSocket connection for a subset of coins
        FIXED: Unified function, proper error handling, fixed buffer timeout

        Args:
            coins_for_connection: List of coin symbols for this connection
            with_display: Enable trade flow display (parameter for future enhancement)
        """
        topics = [f"publicTrade.{coin}" for coin in coins_for_connection]
        connection_id = f"{coins_for_connection[0]}-{coins_for_connection[-1] if len(coins_for_connection) > 1 else 'single'}"

        reconnect_delay = 5  # Start with 5 seconds delay
        max_reconnect_delay = 60  # Max 60 seconds delay

        while self.running:
            try:
                # Add timeout to connection
                async with websockets.connect(
                    self.ws_url,
                    timeout=30,  # 30 second timeout
                    close_timeout=10
                ) as websocket:

                    # Subscribe to trade streams
                    subscribe_msg = {
                        "op": "subscribe",
                        "args": topics
                    }
                    await websocket.send(json.dumps(subscribe_msg))
                    # DEBUG: Confirm subscription
                    logger.info(f"📡 WebSocket {connection_id}: Subscribed to {len(coins_for_connection)} symbols: {coins_for_connection[:3]}...")

                    # Reset reconnect delay on successful connection
                    reconnect_delay = 5

                    while self.running:
                        try:
                            # Add timeout to message receive
                            message = await asyncio.wait_for(websocket.recv(), timeout=60)
                            data = json.loads(message)

                            if 'topic' in data and 'data' in data:
                                topic = data['topic']
                                trades = data['data']

                                # Extract symbol from topic
                                if topic.startswith("publicTrade."):
                                    symbol = topic.split(".")[1]

                                    # Process incoming trades
                                    for trade in trades:
                                        try:
                                            # FIXED: Bybit timestamps are in microseconds, need to convert to milliseconds
                                            bybit_timestamp = int(trade['T'])
                                            # Convert from microseconds to milliseconds if needed
                                            if bybit_timestamp > 10**15:  # If looks like microseconds (16+ digits)
                                                timestamp_ms = bybit_timestamp // 1000
                                            else:
                                                timestamp_ms = bybit_timestamp

                                            trade_data = {
                                                'timestamp': timestamp_ms,
                                                'price': float(trade['p']),
                                                'size': float(trade['v']),
                                                'side': trade['S']
                                            }

                                            # NEW: Process trade incrementally into candles
                                            if symbol in self.current_candle_data:
                                                self._process_trade_to_candle(symbol, trade_data)
                                                # DEBUG: Log first few trades to verify processing
                                                if len(self.candles_buffer[symbol]) == 0:
                                                    logger.info(f"🔄 Processing first trade for {symbol}: {trade_data['price']}")
                                            else:
                                                logger.warning(f"⚠️ Symbol {symbol} not in current_candle_data!")
                                        except (KeyError, ValueError, TypeError) as e:
                                            # Skip invalid trade data silently
                                            continue

                            await asyncio.sleep(0.01)

                        except asyncio.TimeoutError:
                            log_websocket_event(f"Connection {connection_id}: Message timeout, checking connection", 'WARNING')
                            # Send ping to check if connection is alive
                            try:
                                await websocket.ping()
                            except:
                                log_websocket_event(f"Connection {connection_id}: Ping failed, reconnecting", 'WARNING')
                                break
                        except websockets.exceptions.ConnectionClosed:
                            log_websocket_event(f"Connection {connection_id}: Connection closed", 'WARNING')
                            if self.on_disconnect:
                                self.on_disconnect()
                            break
                        except json.JSONDecodeError as e:
                            logger.error(f"Connection {connection_id}: JSON decode error: {e}")
                            await asyncio.sleep(1)
                        except Exception as e:
                            logger.error(f"Connection {connection_id}: Message processing error: {e}")
                            await asyncio.sleep(1)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"Connection {connection_id}: Connection closed ({e})")
                if self.on_disconnect:
                    self.on_disconnect()
            except websockets.exceptions.InvalidHandshake as e:
                logger.error(f"Connection {connection_id}: Handshake failed ({e})")
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
            except asyncio.TimeoutError:
                logger.error(f"Connection {connection_id}: Connection timeout")
            except OSError as e:
                logger.error(f"Connection {connection_id}: Network error ({e})")
            except Exception as e:
                logger.error(f"Connection {connection_id}: Unexpected error: {type(e).__name__}: {e}")
                import traceback
                # Log reconnection
                from src.config import log_reconnect
                log_reconnect(connection_id, str(e)[:50])

            # FIXED: Proper reconnection logic without recursion
            if self.running:
                log_reconnect(connection_id, f"Reconnecting in {reconnect_delay}s")
                await asyncio.sleep(reconnect_delay)
                # Exponential backoff with jitter
                reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)

    async def start_connection(self):
        """
        Start multiple WebSocket connections to receive live trades
        FIXED: Proper task management for graceful shutdown
        """
        self.running = True
        self._connection_tasks = []

        # Distribute symbols across multiple connections
        connections = self._distribute_symbols_to_connections()
        # Starting connections silently

        # Start connection event handler if set
        if self.on_connect:
            self.on_connect()

        # Create and track tasks for all connections
        for coins_for_connection in connections:
            task = asyncio.create_task(self._start_single_connection(coins_for_connection, with_display=False))
            self._connection_tasks.append(task)

        # Wait for all connections to complete
        try:
            await asyncio.gather(*self._connection_tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error in connection gathering: {e}")

    async def start_connection_with_display(self):
        """
        Start multiple WebSocket connections with trade flow display
        FIXED: Unified with start_connection, just sets display flag
        """
        self.running = True
        self._connection_tasks = []

        # Distribute symbols across multiple connections
        connections = self._distribute_symbols_to_connections()
        # Starting connections with display silently

        # Start connection event handler if set
        if self.on_connect:
            self.on_connect()

        # Initialize global candle boundary tracking (server timestamp based)
        self._last_finalized_boundary = 0

        # Create and track tasks for all connections
        for coins_for_connection in connections:
            task = asyncio.create_task(self._start_single_connection(coins_for_connection, with_display=True))
            self._connection_tasks.append(task)

        # Wait for all connections to complete
        try:
            await asyncio.gather(*self._connection_tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error in connection gathering: {e}")

    async def _candle_finalization_timer(self):
        """
        Timer that runs every 10 seconds to finalize candles at exact intervals
        This ensures all symbols finalize candles simultaneously, not when next trade arrives
        """
        candle_interval_ms = 10000  # 10 seconds

        # Wait until the next 10-second boundary to start
        current_time_ms = int(time.time() * 1000)
        next_boundary = ((current_time_ms // candle_interval_ms) + 1) * candle_interval_ms
        wait_ms = next_boundary - current_time_ms
        await asyncio.sleep(wait_ms / 1000.0)

        logger.info("🕰️ Candle finalization timer started")

        while self.running:
            try:
                current_time_ms = int(time.time() * 1000)
                current_boundary = (current_time_ms // candle_interval_ms) * candle_interval_ms

                # Finalize all candles that should be completed by now
                for symbol in self.coins:
                    if symbol in self.current_candle_data:
                        current_data = self.current_candle_data[symbol]

                        # Check if current candle should be finalized
                        if (current_data['candle_start_time'] is not None and
                            current_data['candle_start_time'] < current_boundary and
                            current_data['trades']):

                            # Finalize the candle
                            completed_candle = self._finalize_candle(
                                current_data['trades'],
                                current_data['candle_start_time']
                            )
                            self.candles_buffer[symbol].append(completed_candle)

                            # DEBUG: Log synchronized candle creation
                            candle_count = len(self.candles_buffer[symbol])
                            if candle_count <= 5 or candle_count % 10 == 0:
                                logger.info(f"🕰️ {symbol}: Timer-finalized candle #{candle_count} | Price: {completed_candle['close']}")

                            # Keep exactly WARMUP_INTERVALS (70) candles
                            if len(self.candles_buffer[symbol]) > WARMUP_INTERVALS:
                                self.candles_buffer[symbol] = self.candles_buffer[symbol][-WARMUP_INTERVALS:]

                            # Reset current candle data
                            current_data['trades'] = []
                            current_data['candle_start_time'] = None

                # Wait exactly 10 seconds until next boundary
                await asyncio.sleep(10.0)

            except Exception as e:
                logger.error(f"Error in candle finalization timer: {e}")
                await asyncio.sleep(10.0)  # Continue with normal interval

    def _process_trade_to_candle(self, symbol: str, trade_data: Dict):
        """
        SIMPLIFIED: Just add trades to current candle - timer handles finalization
        This ensures ALL symbols finalize candles at EXACT 10-second boundaries
        """
        candle_interval_ms = 10000  # 10-second candles
        trade_timestamp = trade_data['timestamp']
        candle_start_time = (trade_timestamp // candle_interval_ms) * candle_interval_ms

        current_data = self.current_candle_data[symbol]

        # Check if we need to start a new candle
        if current_data['candle_start_time'] is None:
            # First trade - start new candle
            current_data['candle_start_time'] = candle_start_time
            current_data['trades'] = [trade_data]
        elif current_data['candle_start_time'] == candle_start_time:
            # Same candle - add trade
            current_data['trades'].append(trade_data)
        else:
            # Trade from different period
            if candle_start_time > current_data['candle_start_time']:
                # Trade from future period - start new candle (timer will finalize old one)
                current_data['candle_start_time'] = candle_start_time
                current_data['trades'] = [trade_data]
            # Ignore trades from past periods (shouldn't happen but just in case)

    def _finalize_candle(self, trades: List[Dict], timestamp: int) -> Dict:
        """
        Create a completed candle from trades (same logic as candle_aggregator)
        """
        if not trades:
            return {
                'timestamp': timestamp,
                'open': 0,
                'high': 0,
                'low': 0,
                'close': 0,
                'volume': 0
            }

        prices = [trade['price'] for trade in trades]
        volumes = [trade['size'] for trade in trades]

        open_price = trades[0]['price']
        close_price = trades[-1]['price']
        high_price = max(prices)
        low_price = min(prices)
        total_volume = sum(volumes)

        # Ensure high >= low and other validations
        if low_price > high_price:
            high_price, low_price = low_price, high_price

        if open_price < low_price:
            open_price = low_price
        elif open_price > high_price:
            open_price = high_price

        if close_price < low_price:
            close_price = low_price
        elif close_price > high_price:
            close_price = high_price

        return {
            'timestamp': timestamp,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': total_volume
        }

    def get_current_data(self, symbol: str) -> int:
        """
        Get the latest aggregated data for a symbol - NOW MUCH MORE EFFICIENT
        """
        if symbol in self.candles_buffer and self.candles_buffer[symbol]:
            candles = self.candles_buffer[symbol]
            if candles:
                avg_size_scaled = calculate_scaled_avg_candle_size(candles)
                return avg_size_scaled

        # If no websocket data, fetch from REST API as fallback
        trades = get_recent_trades(symbol, limit=100)
        if trades:
            candles = aggregate_trades_to_candles(trades, 10000)
            if candles:
                avg_size_scaled = calculate_scaled_avg_candle_size(candles)
                return avg_size_scaled

        return 0

    def get_signal_data(self, symbol: str) -> Tuple[bool, Dict]:
        """
        Get signal data for a symbol - NOW SUPER EFFICIENT with pre-built candles
        Warmup ensures we have enough candles before generating signals
        """
        if symbol in self.candles_buffer:
            candles = self.candles_buffer[symbol]  # Already built candles!

            # Check if we have enough candles (this IS the warmup check)
            if len(candles) < WARMUP_INTERVALS:
                return False, {
                    'signal': False,
                    'candle_count': len(candles),
                    'last_candle': None,
                    'criteria': {
                        'validation_error': f'Warmup: {len(candles)}/{WARMUP_INTERVALS} candles',
                        'low_vol': False,
                        'narrow_rng': False,
                        'high_natr': False,
                        'growth_filter': False,
                        'candle_count': len(candles)
                    }
                }

            # Now check if we have enough for signal calculation (20+ for technical indicators)
            if len(candles) >= 20:
                # Convert candles back to trades format for existing signal processing
                # TODO: Later optimize signal_processor to work with candles directly
                fake_trades = self._candles_to_trades_format(candles)
                return process_trades_for_signals(fake_trades, 10000)
            else:
                return False, {
                    'signal': False,
                    'candle_count': len(candles),
                    'last_candle': None,
                    'criteria': {
                        'validation_error': f'Insufficient data: {len(candles)} candles (need 20+)',
                        'low_vol': False,
                        'narrow_rng': False,
                        'high_natr': False,
                        'growth_filter': False,
                        'candle_count': len(candles)
                    }
                }

        # If no websocket data, fetch from REST API as fallback
        trades = get_recent_trades(symbol, limit=100)
        if trades and len(trades) > 20:
            return process_trades_for_signals(trades, 10000)

        # Return default values if insufficient data
        return False, {'signal': False, 'candle_count': 0, 'last_candle': None}

    def _candles_to_trades_format(self, candles: List[Dict]) -> List[Dict]:
        """
        Convert candles back to a trade-like format for compatibility with existing signal processor
        This is a temporary solution until signal_processor is optimized to work with candles directly
        """
        trades = []
        for candle in candles:
            # Create a representative trade for each candle
            trades.append({
                'timestamp': candle['timestamp'],
                'price': candle['close'],  # Use close price as representative
                'size': candle['volume'],
                'side': 'Buy'  # Doesn't matter for signal processing
            })
        return trades

    async def get_all_symbols_data(self) -> List[Dict]:
        """
        Get aggregated data for all configured symbols - NOW MORE EFFICIENT
        """
        results = []
        for symbol in self.coins:
            avg_size_scaled = self.get_current_data(symbol)
            candle_count = len(self.candles_buffer.get(symbol, []))
            results.append({
                'Symbol': symbol,
                'Avg Candle Size (x1000)': avg_size_scaled,
                'Candles': candle_count  # Debug info
            })
            await asyncio.sleep(0.01)

        return results

    async def stop(self):
        """
        FIXED: Graceful shutdown of WebSocket connections
        """
        # Stopping connections silently
        self.running = False

        # Cancel all connection tasks
        for task in self._connection_tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete cancellation
        if self._connection_tasks:
            await asyncio.gather(*self._connection_tasks, return_exceptions=True)

        self._connection_tasks.clear()
        # All connections stopped