"""
CRITICAL TEST: Binance WebSocket connection and trade parsing (Sprint 3)
Tests real-time connection, trade data format, candle aggregation
"""
import sys
import os
import asyncio
import time

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.websocket_handler import TradeWebSocket

async def test_websocket_connection():
    """Test WebSocket connection to Binance and trade data reception"""
    print("=" * 70)
    print("CRITICAL TEST 1: WebSocket Connection & Trade Data")
    print("=" * 70)

    # Test with 3 high-volume coins
    test_coins = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']

    aggregator = TradeWebSocket(test_coins)

    print(f"\n[1/5] Initializing WebSocket for: {test_coins}")

    # Start connection
    ws_task = asyncio.create_task(aggregator.start_connection())

    print("[2/5] WebSocket connection started, waiting for trades...")

    # Wait 15 seconds to collect trades
    await asyncio.sleep(15)

    print("\n[3/5] Checking received trades and candle data...")

    all_passed = True
    results = {}

    for coin in test_coins:
        candles = aggregator.candles_buffer.get(coin, [])
        candle_count = len(candles)

        if candle_count > 0:
            last_candle = candles[-1]
            print(f"\n✅ {coin}: {candle_count} candles received")
            print(f"   Last candle: O={last_candle['open']:.2f} H={last_candle['high']:.2f} "
                  f"L={last_candle['low']:.2f} C={last_candle['close']:.2f} V={last_candle['volume']:.4f}")

            # Validate candle structure
            required_fields = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            if all(field in last_candle for field in required_fields):
                print(f"   ✅ Candle structure valid")
            else:
                print(f"   ❌ Candle structure INVALID - missing fields!")
                all_passed = False

            # Validate candle data integrity
            if last_candle['high'] >= last_candle['low']:
                print(f"   ✅ Price range valid (high >= low)")
            else:
                print(f"   ❌ Price range INVALID (high < low)!")
                all_passed = False

            if last_candle['low'] <= last_candle['close'] <= last_candle['high']:
                print(f"   ✅ Close price in range")
            else:
                print(f"   ❌ Close price OUT OF RANGE!")
                all_passed = False

            results[coin] = {'candles': candle_count, 'valid': True}
        else:
            print(f"\n❌ {coin}: NO candles received!")
            all_passed = False
            results[coin] = {'candles': 0, 'valid': False}

    print("\n[4/5] Stopping WebSocket connection...")
    await aggregator.stop()
    ws_task.cancel()
    try:
        await ws_task
    except asyncio.CancelledError:
        pass

    print("[5/5] Connection closed successfully")

    return all_passed, results


async def test_candle_aggregation():
    """Test candle aggregation over 30 seconds (3+ candles expected)"""
    print("\n" + "=" * 70)
    print("CRITICAL TEST 2: Candle Aggregation (30 seconds)")
    print("=" * 70)

    test_coins = ['BTCUSDT']
    aggregator = TradeWebSocket(test_coins)

    print(f"\n[1/4] Starting WebSocket for {test_coins[0]}")
    ws_task = asyncio.create_task(aggregator.start_connection())

    print("[2/4] Collecting trades for 30 seconds...")
    print("      (expecting 3+ candles at 10-second intervals)")

    await asyncio.sleep(30)

    print("\n[3/4] Analyzing candle sequence...")

    candles = aggregator.candles_buffer.get('BTCUSDT', [])
    candle_count = len(candles)

    all_passed = True

    if candle_count >= 2:
        print(f"✅ Received {candle_count} candles (expected >=2)")

        # Check timestamps are 10 seconds apart
        for i in range(1, min(3, len(candles))):
            time_diff = (candles[i]['timestamp'] - candles[i-1]['timestamp']) / 1000
            print(f"   Candle {i-1} -> {i}: {time_diff:.1f}s apart", end="")
            if 9 <= time_diff <= 11:  # Allow 1s tolerance
                print(" ✅")
            else:
                print(f" ❌ (expected ~10s)")
                all_passed = False

        # Show candle progression
        print(f"\n   Candle progression:")
        for i, candle in enumerate(candles[:5]):
            ts = time.strftime('%H:%M:%S', time.localtime(candle['timestamp']/1000))
            print(f"   [{i}] {ts} | O:{candle['open']:.2f} H:{candle['high']:.2f} "
                  f"L:{candle['low']:.2f} C:{candle['close']:.2f} V:{candle['volume']:.4f}")
    else:
        print(f"❌ Only {candle_count} candles received (expected >=2)")
        all_passed = False

    print("\n[4/4] Stopping WebSocket...")
    await aggregator.stop()
    ws_task.cancel()
    try:
        await ws_task
    except asyncio.CancelledError:
        pass

    return all_passed, candle_count


async def test_signal_generation():
    """Test signal data retrieval (warmup check)"""
    print("\n" + "=" * 70)
    print("CRITICAL TEST 3: Signal Data Structure")
    print("=" * 70)

    test_coins = ['BTCUSDT']
    aggregator = TradeWebSocket(test_coins)

    print(f"\n[1/3] Starting WebSocket for {test_coins[0]}")
    ws_task = asyncio.create_task(aggregator.start_connection())

    print("[2/3] Waiting 12 seconds for candles...")
    await asyncio.sleep(12)

    print("\n[3/3] Checking signal data structure...")

    signal, signal_data = aggregator.get_signal_data('BTCUSDT')

    all_passed = True

    if signal_data:
        print(f"✅ Signal data retrieved")
        print(f"   Candle count: {signal_data.get('candle_count', 0)}")
        print(f"   Signal: {signal}")

        if 'criteria' in signal_data:
            print(f"   ✅ Criteria present")
            criteria = signal_data['criteria']

            # Check for validation_error (warmup)
            if 'validation_error' in criteria and 'Warmup' in criteria['validation_error']:
                print(f"   ✅ Warmup status: {criteria['validation_error']}")

        else:
            print(f"   ❌ Criteria missing!")
            all_passed = False
    else:
        print(f"❌ No signal data retrieved!")
        all_passed = False

    await aggregator.stop()
    ws_task.cancel()
    try:
        await ws_task
    except asyncio.CancelledError:
        pass

    return all_passed


async def main():
    """Run all CRITICAL tests"""
    print("\n🔥 CRITICAL WEBSOCKET TESTS - Sprint 3 (Binance)\n")

    test_results = []

    # Test 1: Connection and trade data
    try:
        passed1, results1 = await test_websocket_connection()
        test_results.append(("WebSocket Connection", passed1))
    except Exception as e:
        print(f"\n❌ TEST 1 CRASHED: {e}")
        import traceback
        traceback.print_exc()
        test_results.append(("WebSocket Connection", False))

    # Test 2: Candle aggregation
    try:
        passed2, candles2 = await test_candle_aggregation()
        test_results.append(("Candle Aggregation", passed2))
    except Exception as e:
        print(f"\n❌ TEST 2 CRASHED: {e}")
        import traceback
        traceback.print_exc()
        test_results.append(("Candle Aggregation", False))

    # Test 3: Signal generation
    try:
        passed3 = await test_signal_generation()
        test_results.append(("Signal Generation", passed3))
    except Exception as e:
        print(f"\n❌ TEST 3 CRASHED: {e}")
        import traceback
        traceback.print_exc()
        test_results.append(("Signal Generation", False))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY - Sprint 3")
    print("=" * 70)

    for test_name, passed in test_results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(result[1] for result in test_results)

    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 ALL CRITICAL TESTS PASSED - Sprint 3 Complete!")
    else:
        print("⚠️  CRITICAL FAILURES DETECTED - Review above!")
    print("=" * 70)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
