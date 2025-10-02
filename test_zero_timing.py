"""
Analyze WHEN zero-price trades arrive
"""
import asyncio
from datetime import datetime
from src.websocket_handler import TradeWebSocket
from src.config import setup_logging, start_candle_logging

# Track zero trades
zero_trades = []

# Monkey-patch to intercept zero trades
original_process = TradeWebSocket._process_trade_to_candle

async def tracked_process(self, symbol, trade_data):
    return await original_process(self, symbol, trade_data)

async def main():
    setup_logging()
    start_candle_logging()

    test_coins = ['TRUTHUSDT']

    print(f"\nZERO TRADE TIMING ANALYSIS")
    print(f"Monitoring: {test_coins}")
    print(f"Duration: 60 seconds")
    print(f"{'='*60}\n")

    aggregator = TradeWebSocket(test_coins)

    # Count real trades
    real_trade_count = {}

    ws_task = asyncio.create_task(aggregator.start_connection())

    # Monitor for 60 seconds
    for i in range(60):
        await asyncio.sleep(1)
        # Count trades every second
        for coin in test_coins:
            if coin in aggregator._trades_by_interval:
                total = sum(len(trades) for trades in aggregator._trades_by_interval[coin].values())
                real_trade_count[f"{coin}_{i}"] = total

    print(f"\n{'='*60}")
    print(f"ANALYSIS COMPLETE")
    print(f"{'='*60}\n")

    # Check stderr output for zero trades pattern
    print("Check stderr above for 'ZERO PRICE FROM BINANCE!' messages")
    print("Note the timestamps when they occur\n")

    import os
    os._exit(0)

if __name__ == "__main__":
    asyncio.run(main())
