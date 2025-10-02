"""
Module for handling WebSocket connections to trading APIs
Manages multiple connections, candle aggregation, and synchronized finalization
"""
import asyncio
import websockets
import json
# import logging
import time
from typing import List, Dict, Callable, Optional, Tuple
from src.candle_aggregator import create_candle_from_trades
from src.config import WARMUP_INTERVALS, log_websocket_event, log_reconnect

# Configure logging
# logger = logging.getLogger(__name__)


class TradeWebSocket:
    def __init__(self, coins: List[str], ws_url: str = "wss://fstream.binance.com/ws", max_connections: int = 12, max_coins_per_connection: int = 200):
        """
        Initialize WebSocket connections for trade data (Binance Futures)
        Uses multiple connections to distribute symbols and avoid limits
        Binance allows up to 200 streams per connection
        """
        self.coins = coins
        self.ws_url = ws_url
        self.max_connections = max_connections
        self.max_coins_per_connection = max_coins_per_connection
        # Store pre-built candles for efficient signal processing
        self.candles_buffer = {}        # Completed candles for each coin
        self.current_candle_data = {}   # Current incomplete candle data per coin
        self.running = False
        self._connection_tasks = []  # Track connection tasks for graceful shutdown
        self._start_time = time.time() # Track when system started for warmup
        self._candle_locks = {}         # Locks to prevent race conditions during finalization
        self._trades_by_interval = {}   # Store trades by 10-second intervals for each coin
        self._seen_trade_signatures = {}  # Track seen trades for deduplication (timestamp_price_size)
        self._candle_sequence = 0       # Global sequence for log ordering

        # Connection stability improvements
        self._connection_stats = {}     # Track connection statistics
        self._reconnect_count = {}      # Track reconnection attempts

        # Initialize candle buffers for each coin
        for coin in self.coins:
            self.candles_buffer[coin] = []         # List of completed candles
            self.current_candle_data[coin] = {     # Current candle being built
                'trades': [],
                'candle_start_time': None,
                'last_finalized_boundary': 0,      # Track last finalized boundary to prevent gaps
                'last_close_price': None           # For forward-fill when no trades
            }
            self._candle_locks[coin] = asyncio.Lock()  # Lock for each coin
            self._trades_by_interval[coin] = {}    # Store trades by 10-second intervals
            self._seen_trade_signatures[coin] = set()  # Deduplication tracking per coin

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
        from src.config import log_reconnect
        # Binance uses combined streams: wss://fstream.binance.com/stream?streams=btcusdt@trade/ethusdt@trade
        streams = [f"{coin.lower()}@trade" for coin in coins_for_connection]
        # Fix: Config has /ws, need /stream for combined streams
        base = self.ws_url.replace('/ws', '/stream') if '/ws' in self.ws_url else self.ws_url
        stream_url = f"{base}?streams={'/'.join(streams)}"
        connection_id = f"{coins_for_connection[0]}-{coins_for_connection[-1] if len(coins_for_connection) > 1 else 'single'}"

        # Initialize connection stats
        if connection_id not in self._connection_stats:
            self._connection_stats[connection_id] = {
                'connect_time': 0,
                'disconnect_time': 0,
                'message_count': 0,
                'last_message_time': 0
            }
        
        if connection_id not in self._reconnect_count:
            self._reconnect_count[connection_id] = 0

        reconnect_delay = 1
        max_reconnect_delay = 30  # Increased max delay
        consecutive_failures = 0

        while self.running:
            try:
                connect_start = time.time()
                async with websockets.connect(
                    stream_url,
                    ping_interval=None,  # Let Binance server handle ping (every 3 min)
                    ping_timeout=None,   # No client-side pong timeout
                    close_timeout=10,
                    max_size=2**20,      # 1MB max message size
                    compression=None,    # Disable compression for stability
                    max_queue=1024       # Increase queue size for high-volume periods
                ) as websocket:

                    # Update connection stats
                    self._connection_stats[connection_id]['connect_time'] = connect_start
                    self._reconnect_count[connection_id] = 0  # Reset on successful connection

                    # Log connection
                    log_websocket_event(f"Connection {connection_id}: Connected", 'INFO')

                    # Reset on successful connection
                    reconnect_delay = 1
                    consecutive_failures = 0

                    while self.running:
                        try:
                            # Receive messages with timeout to detect stale connections
                            try:
                                message = await asyncio.wait_for(websocket.recv(), timeout=300)
                                data = json.loads(message)
                                
                                # Update message stats
                                self._connection_stats[connection_id]['message_count'] += 1
                                self._connection_stats[connection_id]['last_message_time'] = time.time()

                                # Binance combined stream format: {"stream":"btcusdt@trade","data":{...}}
                                if 'stream' in data and 'data' in data:
                                    stream = data['stream']
                                    trade = data['data']

                                    # Extract symbol from stream name (e.g., "btcusdt@trade" -> "BTCUSDT")
                                    if '@trade' in stream:
                                        symbol = stream.split('@')[0].upper()

                                        try:
                                            # Binance trade format: T=timestamp(ms), p=price, q=quantity, m=isBuyerMaker
                                            timestamp_ms = int(trade['T'])
                                            price = float(trade['p'])
                                            size = float(trade['q'])

                                            # Binance: m=true means buyer is maker (sell order filled), so it's a sell
                                            side = 'Sell' if trade['m'] else 'Buy'

                                            trade_data = {
                                                'timestamp': timestamp_ms,
                                                'price': price,
                                                'size': size,
                                                'side': side
                                            }

                                            if symbol in self.current_candle_data:
                                                await self._process_trade_to_candle(symbol, trade_data)

                                        except (KeyError, ValueError, TypeError):
                                            continue
                            except asyncio.CancelledError:
                                # Task was cancelled during shutdown
                                break
                                
                        except websockets.exceptions.ConnectionClosed as e:
                            log_websocket_event(f"Connection {connection_id}: Connection closed ({e.code})", 'WARNING')
                            self._connection_stats[connection_id]['disconnect_time'] = time.time()
                            if self.on_disconnect:
                                self.on_disconnect()
                            break
                        except json.JSONDecodeError as e:
                            # logger.error(f"Connection {connection_id}: JSON decode error: {e}")
                            await asyncio.sleep(1)
                        except Exception as e:
                            pass  # logger.error(f"Connection {connection_id}: Message processing error: {e}")
                            await asyncio.sleep(1)

            except websockets.exceptions.ConnectionClosed as e:
                consecutive_failures += 1
                self._reconnect_count[connection_id] += 1
                self._connection_stats[connection_id]['disconnect_time'] = time.time()
                if self.on_disconnect:
                    self.on_disconnect()
            except websockets.exceptions.InvalidHandshake as e:
                consecutive_failures += 1
                self._reconnect_count[connection_id] += 1
                log_websocket_event(f"Connection {connection_id}: Invalid handshake: {str(e)[:50]}", 'ERROR')
            except asyncio.TimeoutError:
                consecutive_failures += 1
                self._reconnect_count[connection_id] += 1
                log_websocket_event(f"Connection {connection_id}: Connection timeout", 'ERROR')
            except OSError as e:
                consecutive_failures += 1
                self._reconnect_count[connection_id] += 1
                log_websocket_event(f"Connection {connection_id}: OS error: {str(e)[:50]}", 'ERROR')
            except Exception as e:
                consecutive_failures += 1
                self._reconnect_count[connection_id] += 1
                log_reconnect(connection_id, str(e)[:50])

            # Adaptive reconnect: conservative for always-on system
            if self.running:
                # Very conservative reconnect - avoid hammering Binance
                if consecutive_failures == 1:
                    reconnect_delay = 5  # Initial delay
                elif consecutive_failures <= 3:
                    reconnect_delay = 10  # Short delay
                elif consecutive_failures <= 5:
                    reconnect_delay = 30  # Medium delay
                else:
                    reconnect_delay = 60  # Long delay for persistent issues

                # Log reconnection attempt with stats
                total_reconnects = self._reconnect_count[connection_id]
                log_reconnect(connection_id, f"Attempt {total_reconnects} (failures: {consecutive_failures}) in {reconnect_delay:.1f}s")
                await asyncio.sleep(reconnect_delay)

    async def start_connection(self):
        """
        Start multiple WebSocket connections to receive live trades
        Starts candle finalization timer to ensure synchronized candle creation
        """
        self.running = True
        self._connection_tasks = []

        # Distribute symbols across multiple connections
        connections = self._distribute_symbols_to_connections()

        # Log connection information
        from src.config import log_connection_info
        log_connection_info(len(self.coins))

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
            pass  # logger.error(f"Error in connection gathering: {e}")

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

        pass  # logger.info("🕰️ Candle finalization timer started (with gap-filling)")

        while self.running:
            try:
                current_time_ms = int(time.time() * 1000)
                current_boundary = (current_time_ms // candle_interval_ms) * candle_interval_ms

                # Finalize candles for all symbols
                for symbol in self.coins:
                    if symbol not in self.current_candle_data:
                        continue

                    # Lock access to prevent race with trade processing
                    async with self._candle_locks[symbol]:
                        current_data = self.current_candle_data[symbol]
                        last_boundary = current_data['last_finalized_boundary']

                        # If first candle ever, wait for first trade
                        if last_boundary == 0 and current_data['candle_start_time'] is None:
                            continue

                        # Set starting boundary
                        if last_boundary == 0:
                            if current_data['candle_start_time'] is not None:
                                # First candle - use the candle_start_time from first trade
                                last_boundary = current_data['candle_start_time']
                            else:
                                # No trades yet for this symbol, skip to next symbol
                                continue

                        # Create ALL candles from last_boundary to current_boundary
                        boundary = last_boundary
                        while boundary < current_boundary:
                            # Check if we have trades for this specific boundary in _trades_by_interval
                            trades_for_boundary = self._trades_by_interval[symbol].get(boundary, [])
                            if trades_for_boundary:
                                # Have trades for this period - create real candle
                                completed_candle = create_candle_from_trades(
                                    trades_for_boundary,
                                    boundary
                                )
                                # Update last close price for future forward-fill
                                current_data['last_close_price'] = completed_candle['close']
                                
                                # Remove the processed trades from _trades_by_interval
                                del self._trades_by_interval[symbol][boundary]

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
                                # No trades and no last price - this means no previous data for this symbol
                                # We still need to advance the boundary to avoid infinite loop
                                boundary += candle_interval_ms
                                continue

                            # Add sequence number for log ordering
                            completed_candle['_sequence'] = self._candle_sequence
                            self._candle_sequence += 1

                            # Append candle to buffer
                            self.candles_buffer[symbol].append(completed_candle)

                            # Log new candle (async, non-blocking)
                            from src.config import log_new_candle
                            log_new_candle(symbol, completed_candle)

                            # Move to next boundary
                            boundary += candle_interval_ms

                        # Update last finalized boundary
                        current_data['last_finalized_boundary'] = current_boundary

                        # Reset current candle data if it was finalized
                        # Only reset if the current candle start time was within the finalized range
                        if (current_data['candle_start_time'] is not None and
                            current_data['candle_start_time'] < current_boundary):
                            current_data['trades'] = []
                            current_data['candle_start_time'] = None

                # Wait exactly 10 seconds until next boundary
                await asyncio.sleep(10.0)

            except Exception as e:
                pass  # logger.error(f"Error in candle finalization timer: {e}")
                import traceback
                # logger.error(traceback.format_exc())
                await asyncio.sleep(10.0)  # Continue with normal interval

    async def _process_trade_to_candle(self, symbol: str, trade_data: Dict):
        """
        Add trades to current candle - timer handles synchronized finalization
        Trades are accumulated until timer creates the candle
        Uses lock to prevent race with finalization timer
        Includes deduplication to filter duplicate trades (if exchange sends duplicates)
        """
        # Deduplication: Create unique signature for this trade
        signature = f"{trade_data['timestamp']}_{trade_data['price']}_{trade_data['size']}"

        # Check if we've already seen this exact trade
        if signature in self._seen_trade_signatures[symbol]:
            # Skip duplicate trade - already processed
            return

        # Mark this trade as seen
        self._seen_trade_signatures[symbol].add(signature)

        # Periodic cleanup: Remove old signatures to prevent memory growth
        # Keep only signatures from last 60 seconds (6 candle intervals)
        if len(self._seen_trade_signatures[symbol]) > 1000:
            current_time_ms = trade_data['timestamp']
            cutoff_time = current_time_ms - 60000  # 60 seconds ago
            # Remove signatures for trades older than cutoff
            self._seen_trade_signatures[symbol] = {
                sig for sig in self._seen_trade_signatures[symbol]
                if int(sig.split('_')[0]) >= cutoff_time
            }

        candle_interval_ms = 10000  # 10-second candles
        trade_timestamp = trade_data['timestamp']
        candle_start_time = (trade_timestamp // candle_interval_ms) * candle_interval_ms

        async with self._candle_locks[symbol]:
            # Use the trades_by_interval to store trades by their specific interval
            interval_key = candle_start_time
            if interval_key not in self._trades_by_interval[symbol]:
                self._trades_by_interval[symbol][interval_key] = []

            # Add the trade to its specific interval
            self._trades_by_interval[symbol][interval_key].append(trade_data)

            # Update the candle_start_time if this is the first trade or a newer interval
            if (self.current_candle_data[symbol]['candle_start_time'] is None or
                candle_start_time > self.current_candle_data[symbol]['candle_start_time']):
                self.current_candle_data[symbol]['candle_start_time'] = candle_start_time

    def get_signal_data(self, symbol: str) -> Tuple[bool, Dict]:
        """
        Get signal data for a symbol - NOW SUPER EFFICIENT with pre-built candles
        Warmup period waits for minimum candles, then metrics calculated on available data
        """
        if symbol in self.candles_buffer:
            candles = self.candles_buffer[symbol]  # Already built candles!

            # Warmup check: wait for minimum candles before starting signal processing
            if len(candles) < WARMUP_INTERVALS:
                return False, {
                    'signal': False,
                    'candle_count': len(candles),
                    'last_candle': None,
                    'criteria': {
                        'validation_error': f'Warmup: {len(candles)}/{WARMUP_INTERVALS} candles',
                        'low_vol': False,
                        'narrow_rng': False,
                        'high_mma': False,
                        'high_natr': False,  # Keep for backward compatibility
                        'growth_filter': False,
                        'candle_count': len(candles)
                    }
                }

            # After warmup, calculate signals on whatever candles we have
            # Technical indicators will use available data (min 20 for proper calculation)
            from src.signal_processor import generate_signal
            signal, detailed_info = generate_signal(candles)

            signal_data = {
                'signal': signal,
                'candle_count': len(candles),
                'last_candle': candles[-1] if candles else None,
                'criteria': detailed_info
            }
            return signal, signal_data

        return False, {'signal': False, 'candle_count': 0, 'last_candle': None}

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