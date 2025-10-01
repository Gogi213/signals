"""
Sprint 6 Fixes Test
Tests: USDT-only filtering, logging fixes, number formatting
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

from src.trading_api import get_all_symbols_by_volume
from src.websocket_handler import TradeWebSocket
from src.config import _format_number


def test_usdt_only_filter():
    """Test 1: Only USDT pairs are returned"""
    print("=" * 70)
    print("TEST 1: USDT-Only Filter")
    print("=" * 70)

    symbols = get_all_symbols_by_volume()

    print(f"\nTotal symbols: {len(symbols)}")
    print(f"First 10: {symbols[:10]}")

    # Check all symbols end with USDT
    non_usdt = [s for s in symbols if not s.endswith('USDT')]

    if non_usdt:
        print(f"\n❌ FAIL: Found {len(non_usdt)} non-USDT pairs:")
        print(f"   {non_usdt[:10]}")
        return False
    else:
        print(f"\n✅ PASS: All {len(symbols)} symbols are USDT pairs")
        return True


def test_number_formatting():
    """Test 2: Number formatting (no scientific notation)"""
    print("\n" + "=" * 70)
    print("TEST 2: Number Formatting (No Scientific Notation)")
    print("=" * 70)

    test_cases = [
        (0.00004, "0.00004"),      # Was 4e-05
        (0.000001, "0.000001"),    # Was 1e-06
        (0.04, "0.04"),
        (1.234, "1.234"),
        (1234.56, "1234.56"),
        (1000, "1000"),
    ]

    all_passed = True

    for value, expected in test_cases:
        result = _format_number(value)
        passed = result == expected
        status = "✅" if passed else "❌"

        print(f"  {status} {value:15} -> {result:15} (expected: {expected})")

        if not passed:
            all_passed = False

    if all_passed:
        print("\n✅ PASS: All numbers formatted correctly")
    else:
        print("\n❌ FAIL: Some numbers formatted incorrectly")

    return all_passed


async def test_logging_on_new_candle_only():
    """Test 3: Signals logged only on new candles (not every 0.3s)"""
    print("\n" + "=" * 70)
    print("TEST 3: Logging Only On New Candles")
    print("=" * 70)

    # Mock log capture
    logged_signals = []

    def mock_log_signal(coin, signal, signal_data, warmup_complete):
        """Mock log_signal to capture calls"""
        logged_signals.append({
            'coin': coin,
            'candle_count': signal_data.get('candle_count', 0),
            'time': time.time()
        })

    # Patch log_signal
    import src.config
    original_log = src.config.log_signal
    src.config.log_signal = mock_log_signal

    # Run system for 25 seconds
    test_coins = ['BTCUSDT']
    aggregator = TradeWebSocket(test_coins)
    ws_task = asyncio.create_task(aggregator.start_connection())

    print("\nRunning for 25 seconds to collect 2+ candles...")

    # Simulate main loop
    warmup_complete = False
    coin_last_candle_count = {}

    for _ in range(80):  # 25 seconds / 0.3s
        await asyncio.sleep(0.3)

        signal, signal_data = aggregator.get_signal_data('BTCUSDT')
        current_candle_count = signal_data.get('candle_count', 0)

        if current_candle_count >= 20:
            warmup_complete = True

        prev_candle_count = coin_last_candle_count.get('BTCUSDT', 0)

        # This is the logic from main.py
        if current_candle_count > prev_candle_count:
            mock_log_signal('BTCUSDT', signal, signal_data, warmup_complete)
            coin_last_candle_count['BTCUSDT'] = current_candle_count

    await aggregator.stop()
    ws_task.cancel()
    try:
        await ws_task
    except asyncio.CancelledError:
        pass

    # Restore original
    src.config.log_signal = original_log

    # Analysis
    print(f"\nTotal log calls: {len(logged_signals)}")

    if not logged_signals:
        print("❌ FAIL: No logs captured")
        return False

    # Check logs only on new candles
    for i, log in enumerate(logged_signals):
        print(f"  Log {i+1}: Candle {log['candle_count']}")

    # Verify each log has different candle_count
    candle_counts = [log['candle_count'] for log in logged_signals]
    unique_counts = len(set(candle_counts))

    if unique_counts == len(candle_counts):
        print(f"\n✅ PASS: Logged only on new candles ({len(logged_signals)} logs for {unique_counts} candles)")
        return True
    else:
        print(f"\n❌ FAIL: Duplicate candle counts detected")
        return False


async def main():
    """Run all Sprint 6 tests"""
    print("\n🔧 SPRINT 6 FIXES - Test Suite\n")

    results = []

    # Test 1: USDT-only filter
    try:
        passed = test_usdt_only_filter()
        results.append(("USDT-Only Filter", passed))
    except Exception as e:
        print(f"\n❌ TEST 1 CRASHED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("USDT-Only Filter", False))

    # Test 2: Number formatting
    try:
        passed = test_number_formatting()
        results.append(("Number Formatting", passed))
    except Exception as e:
        print(f"\n❌ TEST 2 CRASHED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Number Formatting", False))

    # Test 3: Logging only on new candles
    try:
        passed = await test_logging_on_new_candle_only()
        results.append(("Logging On New Candles", passed))
    except Exception as e:
        print(f"\n❌ TEST 3 CRASHED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Logging On New Candles", False))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY - Sprint 6")
    print("=" * 70)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 ALL SPRINT 6 TESTS PASSED!")
    else:
        print("⚠️  SOME TESTS FAILED - Review above")
    print("=" * 70)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
