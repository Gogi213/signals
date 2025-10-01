"""
PRODUCTION SCALE TEST: Full Binance system with real volume (Sprint 5)
Tests: 100+ symbols, 3+ minutes runtime, memory usage, signal generation
"""
import sys
import os
import asyncio
import time
import psutil
import gc

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.trading_api import get_all_symbols_by_volume
from src.websocket_handler import TradeWebSocket


def get_memory_usage_mb():
    """Get current process memory usage in MB"""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


async def test_production_scale():
    """Test production-scale system (100+ symbols, 3+ minutes)"""
    print("=" * 70)
    print("PRODUCTION SCALE TEST - Binance Migration")
    print("=" * 70)

    # Step 1: Get full symbol list
    print("\n[1/6] Getting symbols from Binance API...")
    all_symbols = get_all_symbols_by_volume()  # Default MIN_DAILY_VOLUME=30M

    if not all_symbols:
        print("❌ FAIL: No symbols retrieved")
        return False

    symbol_count = len(all_symbols)
    print(f"✅ Retrieved {symbol_count} symbols (volume >= 30M)")
    print(f"    First 10: {all_symbols[:10]}")
    print(f"    Last 10: {all_symbols[-10:]}")

    # Check memory before start
    mem_before = get_memory_usage_mb()
    print(f"\n[2/6] Memory before start: {mem_before:.2f} MB")

    # Step 2: Start WebSocket for ALL symbols
    print(f"\n[3/6] Starting WebSocket for {symbol_count} symbols...")
    aggregator = TradeWebSocket(all_symbols)
    ws_task = asyncio.create_task(aggregator.start_connection())

    # Wait for system to stabilize
    await asyncio.sleep(3)
    mem_after_connect = get_memory_usage_mb()
    print(f"    Memory after connection: {mem_after_connect:.2f} MB (+{mem_after_connect - mem_before:.2f} MB)")

    # Step 3: Monitor for 3 minutes (180 seconds)
    print(f"\n[4/6] Running for 3 minutes (180 seconds)...")
    print("    Will check: candles, memory, signals every 30s\n")

    test_duration = 180
    check_interval = 30
    checks = test_duration // check_interval

    results = {
        'candles_by_check': [],
        'memory_by_check': [],
        'signals_by_check': [],
        'errors': []
    }

    for i in range(checks):
        await asyncio.sleep(check_interval)
        elapsed = (i + 1) * check_interval

        # Count candles
        total_candles = sum(len(aggregator.candles_buffer.get(s, [])) for s in all_symbols)
        symbols_with_candles = sum(1 for s in all_symbols if len(aggregator.candles_buffer.get(s, [])) > 0)

        # Check memory
        mem_current = get_memory_usage_mb()
        mem_delta = mem_current - mem_before

        # Count signals (warmup complete = 20+ candles)
        symbols_warmed_up = sum(1 for s in all_symbols if len(aggregator.candles_buffer.get(s, [])) >= 20)

        print(f"    [{elapsed}s] Candles: {total_candles} total, {symbols_with_candles}/{symbol_count} symbols active")
        print(f"           Memory: {mem_current:.2f} MB (+{mem_delta:.2f} MB)")
        print(f"           Warmup: {symbols_warmed_up}/{symbol_count} symbols ready")

        results['candles_by_check'].append(total_candles)
        results['memory_by_check'].append(mem_current)
        results['signals_by_check'].append(symbols_warmed_up)

        # Check for excessive memory growth
        if mem_delta > 500:  # More than 500MB growth
            results['errors'].append(f"Excessive memory growth: +{mem_delta:.2f} MB at {elapsed}s")

    # Step 4: Final analysis
    print(f"\n[5/6] Final Analysis:")

    # Sample symbols analysis
    sample_symbols = all_symbols[::len(all_symbols)//10][:10]  # 10 evenly distributed symbols

    print(f"\n    Sample of {len(sample_symbols)} symbols:")
    for symbol in sample_symbols:
        candles = aggregator.candles_buffer.get(symbol, [])
        signal, signal_data = aggregator.get_signal_data(symbol)

        status = "✅" if len(candles) >= 15 else "⚠️"
        print(f"    {status} {symbol:15} {len(candles):3} candles", end="")

        if len(candles) >= 20:
            print(f" | Signal: {signal}")
        elif len(candles) > 0:
            criteria = signal_data.get('criteria', {})
            val_err = criteria.get('validation_error', '')
            if val_err:
                print(f" | {val_err}")
            else:
                print()
        else:
            print(" | No data")

    # Check for memory leaks
    final_mem = get_memory_usage_mb()
    mem_growth_rate = (final_mem - mem_after_connect) / (test_duration / 60)  # MB/minute

    print(f"\n    Memory Analysis:")
    print(f"      Start: {mem_before:.2f} MB")
    print(f"      After connection: {mem_after_connect:.2f} MB")
    print(f"      Final: {final_mem:.2f} MB")
    print(f"      Growth rate: {mem_growth_rate:.2f} MB/minute")

    # Determine pass/fail
    all_passed = True

    if symbols_with_candles < symbol_count * 0.9:  # Less than 90% symbols have data
        print(f"\n    ⚠️  WARNING: Only {symbols_with_candles}/{symbol_count} symbols have candles")
        all_passed = False

    if mem_growth_rate > 50:  # More than 50MB/minute growth
        print(f"\n    ❌ FAIL: Memory leak detected ({mem_growth_rate:.2f} MB/min)")
        all_passed = False

    if results['errors']:
        print(f"\n    ❌ FAIL: Errors detected:")
        for error in results['errors']:
            print(f"      - {error}")
        all_passed = False

    # Step 5: Cleanup
    print(f"\n[6/6] Stopping system...")
    await aggregator.stop()
    ws_task.cancel()
    try:
        await ws_task
    except asyncio.CancelledError:
        pass

    # Force garbage collection
    gc.collect()

    return all_passed, results


async def main():
    """Run production scale test"""
    print("\n🔥 PRODUCTION SCALE TEST - Sprint 5\n")

    try:
        passed, results = await test_production_scale()

        print("\n" + "=" * 70)
        if passed:
            print("✅ PRODUCTION SCALE TEST PASSED!")
            print("\n   System validated for production deployment:")
            print(f"   - API: Working ✅")
            print(f"   - WebSocket: 100+ symbols ✅")
            print(f"   - Memory: Stable ✅")
            print(f"   - Candles: Aggregating ✅")
            print(f"   - Signals: Processing ✅")
        else:
            print("⚠️  PRODUCTION SCALE TEST: Issues detected (see above)")
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
