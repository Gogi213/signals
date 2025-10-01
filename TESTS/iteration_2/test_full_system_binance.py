"""
FINAL INTEGRATION TEST: Full system with Binance (Sprint 1+2+3)
Tests: API + WebSocket + Signal Processing
"""
import sys
import os
import asyncio

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.trading_api import get_all_symbols_by_volume
from src.websocket_handler import TradeWebSocket

async def test_full_system():
    """Test full system end-to-end"""
    print("=" * 70)
    print("FINAL INTEGRATION TEST: Full Binance System")
    print("=" * 70)

    # Step 1: Get symbols by volume (API test)
    print("\n[1/5] Getting symbols from Binance API...")
    all_symbols = get_all_symbols_by_volume(min_volume=100000000)  # 100M+ volume

    if not all_symbols:
        print("❌ FAIL: No symbols retrieved from API")
        return False

    test_symbols = all_symbols[:5]  # Top 5 by volume
    print(f"✅ Retrieved {len(all_symbols)} symbols, testing with top 5:")
    print(f"    {test_symbols}")

    # Step 2: Start WebSocket
    print("\n[2/5] Starting WebSocket for top 5 symbols...")
    aggregator = TradeWebSocket(test_symbols)
    ws_task = asyncio.create_task(aggregator.start_connection())

    # Step 3: Wait for candles (25 seconds to ensure at least 2 candles)
    print("[3/5] Collecting trades for 25 seconds...")
    await asyncio.sleep(25)

    # Step 4: Check candles and signals
    print("\n[4/5] Analyzing candles and signals...")

    all_passed = True
    results = []

    for symbol in test_symbols:
        candles = aggregator.candles_buffer.get(symbol, [])
        candle_count = len(candles)

        if candle_count >= 1:
            # Get signal data
            signal, signal_data = aggregator.get_signal_data(symbol)

            print(f"\n{symbol}:")
            print(f"  Candles: {candle_count}")

            if candle_count > 0:
                last = candles[-1]
                print(f"  Last: O={last['open']:.2f} H={last['high']:.2f} "
                      f"L={last['low']:.2f} C={last['close']:.2f} V={last['volume']:.4f}")

            # Check signal data structure
            if 'criteria' in signal_data:
                criteria = signal_data['criteria']
                if 'validation_error' in criteria:
                    print(f"  Status: {criteria['validation_error']}")
                else:
                    print(f"  Signal: {signal}")

                print(f"  ✅ Signal system working")
                results.append((symbol, True))
            else:
                print(f"  ❌ Signal system broken")
                results.append((symbol, False))
                all_passed = False
        else:
            print(f"\n{symbol}:")
            print(f"  ❌ No candles received")
            results.append((symbol, False))
            all_passed = False

    # Step 5: Cleanup
    print("\n[5/5] Stopping system...")
    await aggregator.stop()
    ws_task.cancel()
    try:
        await ws_task
    except asyncio.CancelledError:
        pass

    return all_passed


async def main():
    """Run full system test"""
    print("\n🚀 FINAL INTEGRATION TEST - Binance Migration\n")

    try:
        passed = await test_full_system()

        print("\n" + "=" * 70)
        if passed:
            print("✅ FULL SYSTEM TEST PASSED!")
            print("   - API: Working ✅")
            print("   - WebSocket: Working ✅")
            print("   - Candle Aggregation: Working ✅")
            print("   - Signal Processing: Working ✅")
            print("\n🎉 Binance migration complete and validated!")
        else:
            print("❌ FULL SYSTEM TEST FAILED - Review errors above")
        print("=" * 70)

        return passed

    except Exception as e:
        print(f"\n❌ TEST CRASHED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
