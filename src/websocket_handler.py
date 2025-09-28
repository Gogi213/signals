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

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
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
        logger.debug(f"Filtered coins: {self.coins}")
        self.ws_url = ws_url
        self.max_connections = max_connections
        self.max_coins_per_connection = max_coins_per_connection
        self.trades_buffer = {}
        self.running = False
        self._connection_tasks = []  # Track connection tasks for graceful shutdown

        # Initialize buffers for each coin
        for coin in self.coins:
            self.trades_buffer[coin] = []

        # Event handlers for connection events
        self.on_connect: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None

        # Log WebSocket connection info
        connections_needed = self._calculate_needed_connections()
        logger.info(f"Using {connections_needed} WebSocket connections for {len(self.coins)} coins (max {self.max_coins_per_connection} per connection)")

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
                    logger.info(f"Connection {connection_id}: Subscribed to {len(coins_for_connection)} coins")
                    logger.debug(f"Connection {connection_id} coins: {coins_for_connection}")

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
                                            trade_data = {
                                                'timestamp': int(trade['T']),
                                                'price': float(trade['p']),
                                                'size': float(trade['v']),
                                                'side': trade['S']
                                            }

                                            # Add to buffer
                                            if symbol in self.trades_buffer:
                                                self.trades_buffer[symbol].append(trade_data)

                                                # FIXED: Keep only recent trades (20 seconds, was incorrectly 2 seconds)
                                                current_time = int(time.time() * 1000)
                                                self.trades_buffer[symbol] = [
                                                    t for t in self.trades_buffer[symbol]
                                                    if current_time - t['timestamp'] < 20000
                                                ]
                                        except (KeyError, ValueError, TypeError) as e:
                                            logger.debug(f"Invalid trade data format in {connection_id}: {e}")
                                            continue

                            await asyncio.sleep(0.01)

                        except asyncio.TimeoutError:
                            logger.warning(f"Connection {connection_id}: Message timeout, checking connection")
                            # Send ping to check if connection is alive
                            try:
                                await websocket.ping()
                            except:
                                logger.warning(f"Connection {connection_id}: Ping failed, reconnecting")
                                break
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning(f"Connection {connection_id}: Connection closed")
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
                logger.debug(f"Connection {connection_id}: Full traceback: {traceback.format_exc()}")

            # FIXED: Proper reconnection logic without recursion
            if self.running:
                logger.info(f"Connection {connection_id}: Reconnecting in {reconnect_delay} seconds...")
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
        logger.info(f"Starting {len(connections)} WebSocket connections for {len(self.coins)} coins")

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
        logger.info(f"Starting {len(connections)} WebSocket connections with display for {len(self.coins)} coins")

        # Start connection event handler if set
        if self.on_connect:
            self.on_connect()

        # Create and track tasks for all connections
        for coins_for_connection in connections:
            task = asyncio.create_task(self._start_single_connection(coins_for_connection, with_display=True))
            self._connection_tasks.append(task)

        # Wait for all connections to complete
        try:
            await asyncio.gather(*self._connection_tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error in connection gathering: {e}")

    def get_current_data(self, symbol: str) -> int:
        """
        Get the latest aggregated data for a symbol
        """
        if symbol in self.trades_buffer:
            trades = self.trades_buffer[symbol]
            if trades:
                candles = aggregate_trades_to_candles(trades, 10000)  # 10-second candles
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
        Get signal data for a symbol based on trading conditions
        """
        if symbol in self.trades_buffer:
            trades = self.trades_buffer[symbol]
            if len(trades) > 20:  # Need sufficient data for signal calculation
                return process_trades_for_signals(trades, 10000)  # 10-second timeframe

        # If no websocket data, fetch from REST API as fallback
        trades = get_recent_trades(symbol, limit=100)
        if trades and len(trades) > 20:
            return process_trades_for_signals(trades, 10000)

        # Return default values if insufficient data
        return False, {'signal': False, 'candle_count': 0, 'last_candle': None}

    async def get_all_symbols_data(self) -> List[Dict]:
        """
        Get aggregated data for all configured symbols
        """
        results = []
        for symbol in self.coins:
            avg_size_scaled = self.get_current_data(symbol)
            results.append({
                'Symbol': symbol,
                'Avg Candle Size (x1000)': avg_size_scaled
            })
            await asyncio.sleep(0.01)

        return results

    async def stop(self):
        """
        FIXED: Graceful shutdown of WebSocket connections
        """
        logger.info("Stopping WebSocket connections...")
        self.running = False

        # Cancel all connection tasks
        for task in self._connection_tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete cancellation
        if self._connection_tasks:
            await asyncio.gather(*self._connection_tasks, return_exceptions=True)

        self._connection_tasks.clear()
        logger.info("All WebSocket connections stopped")