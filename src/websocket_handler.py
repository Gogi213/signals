"""
Module for handling WebSocket connections to trading APIs
Manages multiple connections, candle aggregation, and synchronized finalization
"""
import asyncio
import websockets
import json
import logging
import time
from typing import List, Dict, Callable, Optional, Tuple
from src.trading_api import get_recent_trades, filter_symbols_by_volume
from src.candle_aggregator import aggregate_trades_to_candles, create_candle_from_trades
from src.signal_processor import process_trades_for_signals
from src.config import WARMUP_INTERVALS, log_websocket_event, log_reconnect

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
        self.ws_url = ws_url
        self.max_connections = max_connections
        self.max_coins_per_connection = max_coins_per_connection
        # Store pre-built candles for efficient signal processing
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
                'candle_start_time': None,
                'last_finalized_boundary': 0,      # Track last finalized boundary to prevent gaps
                'last_close_price': None           # For forward-fill when no trades
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

    async def _start_single_connection(self, coins_for_connection: List[str]):
        """
        Start a single WebSocket connection for a subset of coins
        Handles trade data reception and incremental candle building

        Args:
            coins_for_connection: List of coin symbols for this connection
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
                                            # Bybit timestamps are in microseconds, convert to milliseconds
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

                                            # Process trade incrementally into candles
                                            if symbol in self.current_candle_data:
                                                self._process_trade_to_candle(symbol, trade_data)
                                            else:
                                                logger.warning(f"⚠️ Symbol {symbol} not in current_candle_data!")
                                        except (KeyError, ValueError, TypeError) as e:
                                            # Skip invalid trade data silently
                                            continue

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

            # Reconnect with exponential backoff
            if self.running:
                log_reconnect(connection_id, f"Reconnecting in {reconnect_delay}s")
                await asyncio.sleep(reconnect_delay)
                # Exponential backoff with jitter
                reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)

    async def start_connection(self):
        """
        Start multiple WebSocket connections to receive live trades
        Starts candle finalization timer to ensure synchronized candle creation
        """
        self.running = True
        self._connection_tasks = []

        # Distribute symbols across multiple connections
        connections = self._distribute_symbols_to_connections()

        # Start connection event handler if set
        if self.on_connect:
            self.on_connect()

        # CRITICAL FIX: Start candle finalization timer
        timer_task = asyncio.create_task(self._candle_finalization_timer())
        self._connection_tasks.append(timer_task)

        # Create and track tasks for all connections
        for coins_for_connection in connections:
            task = asyncio.create_task(self._start_single_connection(coins_for_connection))
            self._connection_tasks.append(task)

        # Wait for all connections to complete
        try:
            await asyncio.gather(*self._connection_tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error in connection gathering: {e}")

    async def _candle_finalization_timer(self):
        """
        Timer that runs every 10 seconds to finalize candles at exact intervals
        Creates ALL candles including periods with no trades (forward-fill)
        This ensures synchronized warmup completion across all symbols
        """
        candle_interval_ms = 10000  # 10 seconds

        # Wait until the next 10-second boundary to start
        current_time_ms = int(time.time() * 1000)
        next_boundary = ((current_time_ms // candle_interval_ms) + 1) * candle_interval_ms
        wait_ms = next_boundary - current_time_ms
        await asyncio.sleep(wait_ms / 1000.0)

        logger.info("🕰️ Candle finalization timer started (with gap-filling)")

        while self.running:
            try:
                current_time_ms = int(time.time() * 1000)
                current_boundary = (current_time_ms // candle_interval_ms) * candle_interval_ms

                # Finalize candles for all symbols
                for symbol in self.coins:
                    if symbol not in self.current_candle_data:
                        continue

                    current_data = self.current_candle_data[symbol]
                    last_boundary = current_data['last_finalized_boundary']

                    # If first candle ever, wait for first trade
                    if last_boundary == 0 and current_data['candle_start_time'] is None:
                        continue

                    # Set starting boundary
                    if last_boundary == 0:
                        # First candle - use the candle_start_time from first trade
                        last_boundary = current_data['candle_start_time']

                    # Create ALL candles from last_boundary to current_boundary
                    boundary = last_boundary
                    while boundary < current_boundary:
                        # Check if we have trades for this specific boundary
                        if (current_data['candle_start_time'] == boundary and
                            current_data['trades']):
                            # Have trades for this period - create real candle
                            completed_candle = create_candle_from_trades(
                                current_data['trades'],
                                boundary
                            )
                            # Update last close price for future forward-fill
                            current_data['last_close_price'] = completed_candle['close']

                        elif current_data['last_close_price'] is not None:
                            # No trades for this period - forward-fill with last price
                            completed_candle = {
                                'timestamp': boundary,
                                'open': current_data['last_close_price'],
                                'high': current_data['last_close_price'],
                                'low': current_data['last_close_price'],
                                'close': current_data['last_close_price'],
                                'volume': 0
                            }
                        else:
                            # No trades and no last price - skip this boundary
                            boundary += candle_interval_ms
                            continue

                        # Append candle to buffer
                        self.candles_buffer[symbol].append(completed_candle)

                        # Move to next boundary
                        boundary += candle_interval_ms

                    # Log only the LAST created candle to avoid spam
                    candle_count = len(self.candles_buffer[symbol])
                    if candle_count > 0:
                        last_candle = self.candles_buffer[symbol][-1]
                        if candle_count <= 5 or candle_count % 10 == 0:
                            volume_str = f"vol:{last_candle['volume']:.0f}" if last_candle['volume'] > 0 else "forward-fill"
                            logger.info(f"🕰️ {symbol}: Candle #{candle_count} | Price: {last_candle['close']} | {volume_str}")

                    # Trim buffer ONCE after all candles created
                    if len(self.candles_buffer[symbol]) > WARMUP_INTERVALS:
                        self.candles_buffer[symbol] = self.candles_buffer[symbol][-WARMUP_INTERVALS:]

                    # Update last finalized boundary
                    current_data['last_finalized_boundary'] = current_boundary

                    # Reset current candle data if it was finalized
                    if current_data['candle_start_time'] is not None and current_data['candle_start_time'] < current_boundary:
                        current_data['trades'] = []
                        current_data['candle_start_time'] = None

                # Wait exactly 10 seconds until next boundary
                await asyncio.sleep(10.0)

            except Exception as e:
                logger.error(f"Error in candle finalization timer: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await asyncio.sleep(10.0)  # Continue with normal interval

    def _process_trade_to_candle(self, symbol: str, trade_data: Dict):
        """
        Add trades to current candle - timer handles synchronized finalization
        Trades are accumulated until timer creates the candle
        """
        candle_interval_ms = 10000  # 10-second candles
        trade_timestamp = trade_data['timestamp']
        candle_start_time = (trade_timestamp // candle_interval_ms) * candle_interval_ms

        current_data = self.current_candle_data[symbol]

        # Check if we need to start a new candle
        if current_data['candle_start_time'] is None:
            # First trade ever - start new candle
            current_data['candle_start_time'] = candle_start_time
            current_data['trades'] = [trade_data]
        elif current_data['candle_start_time'] == candle_start_time:
            # Same candle period - add trade
            current_data['trades'].append(trade_data)
        elif candle_start_time < current_data['candle_start_time']:
            # Trade from past period - ignore (shouldn't happen)
            pass
        else:
            # Trade from future period - means current candle period ended
            # Timer will finalize old candle and we start accumulating for new period
            current_data['candle_start_time'] = candle_start_time
            current_data['trades'] = [trade_data]

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
                # Convert candles to trades format for signal_processor compatibility
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

    async def stop(self):
        """
        Gracefully shutdown all WebSocket connections and timer task
        """
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