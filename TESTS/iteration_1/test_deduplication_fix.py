"""
Quick validation test for deduplication fix
Verifies that the patch removes ~9.4% duplicates
"""
import asyncio
import time
import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.websocket_handler import TradeWebSocket


async def test_deduplication():
    """Verify deduplication is working"""
    print("\n=== DEDUPLICATION FIX VALIDATION ===\n")

    test_coins = ['ARBUSDT', '1000PEPEUSDT', 'AVAXUSDT']
    aggregator = TradeWebSocket(test_coins)

    # Track statistics
    stats = {
        'trades_received': 0,
        'trades_processed': 0,
        'duplicates_filtered': 0
    }

    # Intercept at WebSocket level (before deduplication)
    original_process = aggregator._process_trade_to_candle

    async def track_trades(symbol: str, trade_data):
        stats['trades_received'] += 1

        # Check if will be filtered
        signature = f"{trade_data['timestamp']}_{trade_data['price']}_{trade_data['size']}"
        is_duplicate = signature in aggregator._seen_trade_signatures.get(symbol, set())

        if is_duplicate:
            stats['duplicates_filtered'] += 1

        # Call original (with deduplication)
        await original_process(symbol, trade_data)

        # If not filtered, count as processed
        if not is_duplicate:
            stats['trades_processed'] += 1

    aggregator._process_trade_to_candle = track_trades

    # Run test
    ws_task = asyncio.create_task(aggregator.start_connection())

    print("Running test for 60 seconds...")

    for i in range(6):
        await asyncio.sleep(10)
        if stats['trades_received'] > 0:
            dup_rate = stats['duplicates_filtered'] / stats['trades_received'] * 100
            print(f"[{(i+1)*10}s] Received: {stats['trades_received']}, "
                  f"Filtered: {stats['duplicates_filtered']} ({dup_rate:.2f}%), "
                  f"Processed: {stats['trades_processed']}")

    await aggregator.stop()
    await ws_task

    # Final results
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)

    if stats['trades_received'] > 0:
        dup_rate = stats['duplicates_filtered'] / stats['trades_received'] * 100

        print(f"Total trades received: {stats['trades_received']}")
        print(f"Duplicates filtered: {stats['duplicates_filtered']} ({dup_rate:.2f}%)")
        print(f"Trades processed: {stats['trades_processed']}")
        print(f"Expected duplicate rate: ~9.4%")

        if 7 <= dup_rate <= 15:
            print(f"\n✅ DEDUPLICATION WORKING: {dup_rate:.2f}% filtered (expected ~9.4%)")
        else:
            print(f"\n⚠️  UNEXPECTED RATE: {dup_rate:.2f}% (expected ~9.4%)")
    else:
        print("⚠️  No trades received during test")

    # Check candles created
    total_candles = sum(len(aggregator.candles_buffer.get(coin, [])) for coin in test_coins)
    print(f"\nCandles created: {total_candles}")

    # Show per-coin stats
    print("\nPer-coin breakdown:")
    for coin in test_coins:
        candles = len(aggregator.candles_buffer.get(coin, []))
        print(f"  {coin}: {candles} candles")


async def main():
    try:
        await test_deduplication()
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())