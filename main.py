"""
Main application file for the trading signals system with improved logging
"""
import asyncio
import time
import logging
from typing import List, Dict

from src.websocket_handler import TradeWebSocket
from src.strategy_client import StrategyRunner
from src.config import DEFAULT_STRATEGY_NAMES, DEFAULT_SERVER_URLS, DEFAULT_UPDATE_INTERVAL, MIN_DAILY_VOLUME
from src.trading_api import get_all_symbols_by_volume

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detailed logging
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def send_signal(url: str, strategy_name: str, coin: str, signal: bool):
    """
    Send signal to strategy based on trading conditions
    """
    strategy_url_update = f"http://{url}:3001/update_settings"
    strategy_runner_update = StrategyRunner(strategy_url_update)

    signal_data = {
        "signal_active": signal
    }

    update_strategy_request = {
        "strategy_name": strategy_name,
        "symbol": coin,
        "settings": signal_data
    }

    import json
    data = json.dumps(update_strategy_request, ensure_ascii=False)
    # Only log the signal itself
    if signal:
        logger.info(f"Signal: {coin} - BUY")
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
    logger.debug(f"All filtered coins that will be used: {filtered_coins}")
    logger.info(f"Total number of filtered coins: {len(filtered_coins)}")
    # This will be logged in TradeWebSocket constructor
     
    # Create WebSocket aggregator with filtered coins
    aggregator = TradeWebSocket(filtered_coins)
    
    # Add logging for WebSocket connection events
    def on_connect():
        logger.info("WebSocket connected")
    
    def on_disconnect():
        logger.info("WebSocket disconnected")
    
    # Set up event handlers
    aggregator.on_connect = on_connect
    aggregator.on_disconnect = on_disconnect
    
    # Start WebSocket connection with trade flow display in a separate task
    ws_task = asyncio.create_task(aggregator.start_connection_with_display())
    
    # Keep the connection running and process signals in real-time
    try:
        while True:
            # Check for signals for all symbols in real-time
            for coin in filtered_coins:
                # Get signal data for the coin
                signal, signal_info = aggregator.get_signal_data(coin)
                
                # Send signal immediately if it's True
                if signal:
                    logger.info(f"Signal: {coin} - BUY")
                    await send_signals_loop(coin, signal)
                    # Small delay to avoid overwhelming the system
                    await asyncio.sleep(0.1)
            
            # Check for signals every 0.3 seconds for real-time processing
            await asyncio.sleep(0.3)
    
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        # Stop the WebSocket connection after processing
        await aggregator.stop()


if __name__ == "__main__":
    # Run continuously without fixed intervals for real-time signal processing
    asyncio.run(main())