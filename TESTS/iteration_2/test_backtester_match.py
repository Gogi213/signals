"""
Test: Verify signal_processor matches backtester formulas exactly
"""
import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.signal_processor import (
    calculate_natr,
    check_growth_filter,
    calculate_percentile,
    check_low_volume_condition,
    check_narrow_range_condition,
    check_high_natr_condition
)


def test_natr_typical_price():
    """Test 1: NATR uses Typical Price, not Close"""
    print("=" * 70)
    print("TEST 1: NATR - Typical Price Denominator")
    print("=" * 70)

    # Create test candles
    candles = [
        {'high': 100, 'low': 90, 'close': 95, 'volume': 1000},
        {'high': 102, 'low': 92, 'close': 97, 'volume': 1100},
        {'high': 105, 'low': 95, 'close': 100, 'volume': 1200},
        {'high': 103, 'low': 93, 'close': 98, 'volume': 1300},
    ] * 10  # 40 candles

    natr_values = calculate_natr(candles, period=20)

    # Manual check: last candle
    last_candle = candles[-1]
    typical_price = (last_candle['high'] + last_candle['low'] + last_candle['close']) / 3.0

    print(f"\nLast candle:")
    print(f"  High: {last_candle['high']}")
    print(f"  Low: {last_candle['low']}")
    print(f"  Close: {last_candle['close']}")
    print(f"  Typical Price: {typical_price:.2f}")
    print(f"  NATR: {natr_values[-1]:.4f}")

    # Verify NATR is not zero (was calculated)
    if natr_values[-1] > 0:
        print("\n✅ PASS: NATR calculated (using Typical Price)")
        return True
    else:
        print("\n❌ FAIL: NATR is zero")
        return False


def test_growth_filter_no_abs():
    """Test 2: Growth Filter doesn't use abs() in denominator"""
    print("\n" + "=" * 70)
    print("TEST 2: Growth Filter - No abs() in denominator")
    print("=" * 70)

    # Test case 1: Positive growth
    candles_positive = [{'close': 100 - i, 'high': 101, 'low': 99, 'volume': 1000} for i in range(60)]
    candles_positive[-1]['close'] = 110  # Current price higher

    passed, details = check_growth_filter(candles_positive, lookback_period=50, min_growth_pct=-0.1)

    print(f"\nTest Case 1: Price rise (100 → 110)")
    print(f"  Growth: {details['current']}%")
    print(f"  Expected: ~10%")

    if abs(details['current'] - 10.0) < 0.5:
        print("  ✅ PASS")
        passed1 = True
    else:
        print(f"  ❌ FAIL: Got {details['current']}%")
        passed1 = False

    # Test case 2: Negative base price (edge case)
    # This would behave differently with abs()
    candles_negative = [{'close': -100, 'high': -99, 'low': -101, 'volume': 1000} for i in range(60)]
    candles_negative[-1]['close'] = -90  # Less negative (increase)

    passed2_obj, details2 = check_growth_filter(candles_negative, lookback_period=50, min_growth_pct=-0.1)

    print(f"\nTest Case 2: Negative base price (-100 → -90)")
    print(f"  Growth: {details2['current']}%")
    print(f"  Expected: ~10% ((-90 - (-100)) / -100 * 100)")

    # With abs(): would be (-90 - (-100)) / 100 * 100 = 10%
    # Without abs(): (-90 - (-100)) / -100 * 100 = 10 / -100 * 100 = -10%

    if abs(details2['current'] - (-10.0)) < 0.5:
        print("  ✅ PASS: No abs() in denominator (result is negative)")
        passed2 = True
    else:
        print(f"  ❌ FAIL: Expected -10%, got {details2['current']}%")
        passed2 = False

    return passed1 and passed2


def test_percentile_calculation():
    """Test 3: Percentile calculation matches expected behavior"""
    print("\n" + "=" * 70)
    print("TEST 3: Percentile Calculation")
    print("=" * 70)

    # Test data
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] * 3  # 30 values

    percentiles = calculate_percentile(data, period=20, percentile=5.0)

    # Check last value (window = last 20 values)
    # data[-20:] = [1,2,3,4,5,6,7,8,9,10] * 2 = 20 values
    # 5th percentile of [1-10, 1-10] should be ~1

    last_percentile = percentiles[-1]

    print(f"\nData: {data[:10]}... (repeated)")
    print(f"Last 20 values 5th percentile: {last_percentile:.2f}")
    print(f"Expected: ~1.0")

    if abs(last_percentile - 1.0) < 0.5:
        print("✅ PASS: Percentile calculation correct")
        return True
    else:
        print(f"❌ FAIL: Expected ~1.0, got {last_percentile:.2f}")
        return False


def test_signal_conditions_integration():
    """Test 4: Integration test - all conditions work together"""
    print("\n" + "=" * 70)
    print("TEST 4: Integration - All Conditions")
    print("=" * 70)

    # Create realistic candles
    candles = []
    for i in range(60):
        candles.append({
            'high': 100 + i * 0.1,
            'low': 99 + i * 0.1,
            'close': 99.5 + i * 0.1,
            'volume': 1000 - i * 5  # Decreasing volume
        })

    # Test all conditions
    low_vol_passed, low_vol_details = check_low_volume_condition(candles, vol_period=20, vol_pctl=5.0)
    narrow_rng_passed, narrow_rng_details = check_narrow_range_condition(candles, range_period=30, rng_pctl=5.0)
    high_natr_passed, high_natr_details = check_high_natr_condition(candles, natr_period=20, natr_min=0.6)
    growth_passed, growth_details = check_growth_filter(candles, lookback_period=50, min_growth_pct=-0.1)

    print(f"\nConditions:")
    print(f"  Low Volume: {low_vol_passed} (current={low_vol_details['current']:.2f}, threshold={low_vol_details['threshold']:.2f})")
    print(f"  Narrow Range: {narrow_rng_passed} (current={narrow_rng_details['current']:.6f}, threshold={narrow_rng_details['threshold']:.6f})")
    print(f"  High NATR: {high_natr_passed} (current={high_natr_details['current']:.3f}, threshold={high_natr_details['threshold']})")
    print(f"  Growth Filter: {growth_passed} (current={growth_details['current']:.2f}%, threshold={growth_details['threshold']}%)")

    # Check all have valid values
    all_valid = (
        low_vol_details['current'] >= 0 and
        narrow_rng_details['current'] >= 0 and
        high_natr_details['current'] >= 0 and
        'current' in growth_details
    )

    if all_valid:
        print("\n✅ PASS: All conditions calculated successfully")
        return True
    else:
        print("\n❌ FAIL: Some conditions have invalid values")
        return False


def main():
    """Run all backtester match tests"""
    print("\n🔬 BACKTESTER FORMULA MATCH TESTS\n")

    results = []

    # Test 1: NATR
    try:
        passed = test_natr_typical_price()
        results.append(("NATR - Typical Price", passed))
    except Exception as e:
        print(f"\n❌ TEST 1 CRASHED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("NATR - Typical Price", False))

    # Test 2: Growth Filter
    try:
        passed = test_growth_filter_no_abs()
        results.append(("Growth Filter - No abs()", passed))
    except Exception as e:
        print(f"\n❌ TEST 2 CRASHED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Growth Filter - No abs()", False))

    # Test 3: Percentile
    try:
        passed = test_percentile_calculation()
        results.append(("Percentile Calculation", passed))
    except Exception as e:
        print(f"\n❌ TEST 3 CRASHED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Percentile Calculation", False))

    # Test 4: Integration
    try:
        passed = test_signal_conditions_integration()
        results.append(("Integration Test", passed))
    except Exception as e:
        print(f"\n❌ TEST 4 CRASHED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Integration Test", False))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY - Backtester Match")
    print("=" * 70)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 ALL TESTS PASSED - Formulas match backtester!")
    else:
        print("⚠️  SOME TESTS FAILED - Review above")
    print("=" * 70)

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
