"""
Main application file for the trading signals system
"""
import asyncio
import time
# import logging
from typing import List, Dict

from src.websocket_handler import TradeWebSocket
from src.strategy_client import StrategyRunner
from src.config import (
    DEFAULT_STRATEGY_NAMES, DEFAULT_SERVER_URLS, DEFAULT_UPDATE_INTERVAL,
    MIN_DAILY_VOLUME, build_strategy_url, setup_logging, log_signal, log_connection_info,
    log_warmup_progress, WARMUP_INTERVALS
)
from src.trading_api import get_all_symbols_by_volume

# Setup JSON logging
setup_logging()
# logger = logging.getLogger(__name__)


async def send_signal(url: str, strategy_name: str, coin: str, signal: bool):
    """
    Send signal to strategy based on trading conditions
    """
    strategy_url_update = build_strategy_url(url)
    strategy_runner_update = StrategyRunner(strategy_url_update)

    signal_data = {
        "signal_active": signal
    }

    update_strategy_request = {
        "strategy_name": strategy_name,
        "symbol": coin,
        "settings": signal_data
    }

    await strategy_runner_update.call_with_json(update_strategy_request)


async def send_signals_loop(coin: str, signal: bool):
    """
    Loop through strategy names and server URLs to send signals
    """
    for strategy_name in DEFAULT_STRATEGY_NAMES:
        for url in DEFAULT_SERVER_URLS:
            await asyncio.sleep(0.1)
            await send_signal(url, strategy_name, coin, signal)


async def main():
    """
    Main function to run the trading signals system
    """
    # Get all symbols and filter by volume before creating WebSocket aggregator
    filtered_coins = get_all_symbols_by_volume()

    # Create WebSocket aggregator with filtered coins
    aggregator = TradeWebSocket(filtered_coins)

    # Track coins with no data during warmup period
    excluded_coins = set()
    coin_first_seen = {}  # Track when each coin was first processed
    coin_last_signal = {}  # Track last signal state to avoid spam

    # Log connection info
    log_connection_info(len(filtered_coins))

    # Start WebSocket connection in a separate task
    ws_task = asyncio.create_task(aggregator.start_connection())
    
    # Keep the connection running and process signals in real-time
    last_warmup_log = 0
    try:
        while True:
            # Check for signals for all symbols in real-time
            warmup_active = False
            min_candles = float('inf')

            for coin in filtered_coins:
                # Skip excluded coins
                if coin in excluded_coins:
                    continue

                # Track when coin was first seen
                current_time = time.time()
                if coin not in coin_first_seen:
                    coin_first_seen[coin] = current_time

                # Get signal data for the coin
                signal, signal_info = aggregator.get_signal_data(coin)

                # Check if coin has no data for too long during warmup (exclude after 10 minutes)
                time_since_start = current_time - coin_first_seen[coin]
                if (signal_info and signal_info.get('candle_count', 0) == 0 and
                    time_since_start > 600):  # 10 minutes with no data
                    excluded_coins.add(coin)
                    # logger.warning(f"Excluding {coin} - no trading data for {time_since_start:.0f}s")
                    continue

                # Check if any coin is still warming up
                if signal_info and 'criteria' in signal_info:
                    criteria = signal_info['criteria']
                    if criteria.get('validation_error', '').startswith('Warmup:'):
                        warmup_active = True
                        candle_count = signal_info.get('candle_count', 0)
                        min_candles = min(min_candles, candle_count)

                # Check if signal changed (only send on change)
                prev_signal = coin_last_signal.get(coin, None)

                # Only log and send if signal changed or first time
                if prev_signal is None or prev_signal != signal:
                    # Log signal regardless of whether it's True or False
                    from src.config import log_signal
                    log_signal(coin, signal, signal_info)

                    if signal:
                        await send_signals_loop(coin, signal)
                        # Small delay to avoid overwhelming the system
                        await asyncio.sleep(0.1)

                    # Update last signal state
                    coin_last_signal[coin] = signal

            # Log warmup progress every 10 intervals (or on first candle)
            if warmup_active and min_candles != float('inf'):
                if min_candles - last_warmup_log >= 10 or (min_candles == 1 and last_warmup_log == 0):
                    log_warmup_progress(min_candles, WARMUP_INTERVALS)
                    last_warmup_log = min_candles

            # Check for signals every 0.3 seconds for real-time processing
            await asyncio.sleep(0.3)
    
    except KeyboardInterrupt:
        pass  # logger.info("Shutting down...")
    except Exception as e:
        pass  # logger.error(f"Error: {e}")
    finally:
        # Stop the WebSocket connection after processing
        await aggregator.stop()


if __name__ == "__main__":
    # Run continuously without fixed intervals for real-time signal processing
    asyncio.run(main())