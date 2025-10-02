"""
Quick 30-second test to verify zero price fix
"""
import asyncio
from datetime import datetime
from src.websocket_handler import TradeWebSocket
from src.config import setup_logging, start_candle_logging

async def main():
    setup_logging()
    start_candle_logging()

    test_coins = ['TRUTHUSDT', 'ASTERUSDT']

    print(f"\nQUICK ZERO PRICE TEST - 30 seconds")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}\n")

    aggregator = TradeWebSocket(test_coins)
    ws_task = asyncio.create_task(aggregator.start_connection())
    await asyncio.sleep(30)

    # Check results
    print(f"\nRESULTS:")
    bugs_found = 0
    for coin in test_coins:
        if coin in aggregator.candles_buffer:
            candles = aggregator.candles_buffer[coin]
            print(f"{coin}: {len(candles)} candles")
            for i, c in enumerate(candles):
                if c['low'] == 0 and c['volume'] > 0:
                    bugs_found += 1
                    print(f"  BUG: Candle {i+1} has L=0 but V={c['volume']:.0f}")

    if bugs_found == 0:
        print("\nSUCCESS: No L=0 bugs found!")
    else:
        print(f"\nFAILED: {bugs_found} bugs still present")

    print(f"Completed: {datetime.now().strftime('%H:%M:%S')}\n")

    import os
    os._exit(0)

if __name__ == "__main__":
    asyncio.run(main())
