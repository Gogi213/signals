"""
Final 20-second verification test
"""
import asyncio
import sys
from datetime import datetime
from src.websocket_handler import TradeWebSocket
from src.config import setup_logging, start_candle_logging

async def main():
    setup_logging()
    start_candle_logging()

    test_coins = ['TRUTHUSDT', 'ASTERUSDT']

    print(f"\n{'='*60}")
    print(f"FINAL VERIFICATION TEST - 20 seconds")
    print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}\n", flush=True)

    aggregator = TradeWebSocket(test_coins)
    ws_task = asyncio.create_task(aggregator.start_connection())
    await asyncio.sleep(20)

    # Check for bugs
    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"{'='*60}\n")

    total_bugs = 0
    total_candles = 0

    for coin in test_coins:
        if coin in aggregator.candles_buffer:
            candles = aggregator.candles_buffer[coin]
            total_candles += len(candles)
            print(f"{coin}: {len(candles)} candles created")

            bugs_in_coin = 0
            for i, c in enumerate(candles, 1):
                if c['low'] == 0 and c['volume'] > 0:
                    bugs_in_coin += 1
                    total_bugs += 1
                    print(f"  [BUG] Candle {i}: L=0, V={c['volume']:.0f}")
                    print(f"        O={c['open']}, H={c['high']}, C={c['close']}")

            if bugs_in_coin == 0:
                print(f"  [OK] All candles valid!")
        else:
            print(f"{coin}: No candles")

    print(f"\n{'='*60}")
    if total_bugs == 0:
        print(f"SUCCESS! {total_candles} candles, 0 bugs found")
        print(f"The zero-price filter is working correctly!")
    else:
        print(f"FAILED! {total_bugs} bugs found in {total_candles} candles")
    print(f"Completed: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}\n", flush=True)

    import os
    os._exit(0)

if __name__ == "__main__":
    asyncio.run(main())
