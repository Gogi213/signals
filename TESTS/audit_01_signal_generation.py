"""
AUDIT #1 - Signal Generation Testing
Tests signal calculation logic and criteria validation
"""
import asyncio
import time
from typing import List, Dict
import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.websocket_handler import TradeWebSocket
from src.signal_processor import generate_signal, check_low_volume_condition, check_narrow_range_condition, check_high_natr_condition
from src.candle_aggregator import create_candle_from_trades


async def test_signal_generation_live():
    """Test signal generation with live data"""
    print("\n=== SIGNAL GENERATION TEST (LIVE) ===\n")

    test_coins = ['10000LADYSUSDT', 'ARBUSDT']
    aggregator = TradeWebSocket(test_coins)

    # Track signals over time
    signal_history = []

    # Start connection
    ws_task = asyncio.create_task(aggregator.start_connection())

    print(f"Monitoring signals for 180 seconds (3 minutes)...")
    start_time = time.time()

    while time.time() - start_time < 180:
        for coin in test_coins:
            signal, signal_info = aggregator.get_signal_data(coin)

            if signal_info and signal_info.get('candle_count', 0) > 0:
                signal_history.append({
                    'time': time.time(),
                    'coin': coin,
                    'signal': signal,
                    'candle_count': signal_info.get('candle_count', 0),
                    'criteria': signal_info.get('criteria', {})
                })

        await asyncio.sleep(10)  # Check every 10 seconds

    # Stop
    await aggregator.stop()
    await ws_task

    # ANALYSIS
    print(f"\n📊 Total signal checks: {len(signal_history)}")

    # Group by coin
    by_coin = {}
    for entry in signal_history:
        coin = entry['coin']
        if coin not in by_coin:
            by_coin[coin] = []
        by_coin[coin].append(entry)

    for coin, history in by_coin.items():
        print(f"\n--- {coin} ---")
        print(f"  Total checks: {len(history)}")

        # Count signals
        true_signals = [h for h in history if h['signal']]
        false_signals = [h for h in history if not h['signal']]

        print(f"  True signals: {len(true_signals)}")
        print(f"  False signals: {len(false_signals)}")

        # Check warmup completion
        warmup_complete = [h for h in history if h['candle_count'] >= 25]
        print(f"  Warmup completed: {len(warmup_complete)} / {len(history)}")

        # Show criteria details for last check
        if history:
            last = history[-1]
            print(f"\n  Last check:")
            print(f"    Signal: {last['signal']}")
            print(f"    Candle count: {last['candle_count']}")

            criteria = last['criteria']
            if 'validation_error' in criteria and criteria['validation_error']:
                print(f"    Validation error: {criteria['validation_error']}")
            else:
                print(f"    Criteria:")
                for key, value in criteria.items():
                    if key not in ['validation_error', 'candle_count', 'criteria_details']:
                        print(f"      {key}: {value}")


def test_signal_criteria_isolated():
    """Test individual signal criteria with synthetic data"""
    print("\n=== SIGNAL CRITERIA ISOLATED TEST ===\n")

    # Create synthetic candles
    base_candles = []
    base_price = 100.0

    for i in range(50):
        candle = {
            'timestamp': i * 10000,
            'open': base_price,
            'high': base_price + 0.5,
            'low': base_price - 0.5,
            'close': base_price + (0.1 if i % 2 == 0 else -0.1),
            'volume': 1000.0 + (i * 10)
        }
        base_candles.append(candle)
        base_price = candle['close']

    print(f"Created {len(base_candles)} synthetic candles")

    # Test low volume condition
    print("\n--- Low Volume Condition ---")
    low_vol_passed, low_vol_details = check_low_volume_condition(base_candles)
    print(f"  Passed: {low_vol_passed}")
    print(f"  Details: {low_vol_details}")

    # Test narrow range condition
    print("\n--- Narrow Range Condition ---")
    narrow_rng_passed, narrow_rng_details = check_narrow_range_condition(base_candles)
    print(f"  Passed: {narrow_rng_passed}")
    print(f"  Details: {narrow_rng_details}")

    # Test high NATR condition
    print("\n--- High NATR Condition ---")
    high_natr_passed, high_natr_details = check_high_natr_condition(base_candles)
    print(f"  Passed: {high_natr_passed}")
    print(f"  Details: {high_natr_details}")

    # Test full signal generation
    print("\n--- Full Signal Generation ---")
    signal, detailed_info = generate_signal(base_candles)
    print(f"  Signal: {signal}")
    print(f"  Detailed info: {detailed_info}")

    # Create extreme case - all conditions should pass
    print("\n=== EXTREME CASE: All Conditions Pass ===")
    extreme_candles = []
    for i in range(50):
        # Very low volume at the end, very narrow range, high volatility in history
        volume = 10000.0 if i < 45 else 10.0  # Last 5 candles have very low volume
        range_size = 5.0 if i < 45 else 0.01  # Last candles have narrow range
        base = 100.0 + (i * 0.5)

        candle = {
            'timestamp': i * 10000,
            'open': base,
            'high': base + range_size,
            'low': base,
            'close': base + range_size * 0.5,
            'volume': volume
        }
        extreme_candles.append(candle)

    extreme_signal, extreme_info = generate_signal(extreme_candles)
    print(f"  Signal: {extreme_signal}")
    print(f"  Detailed info:")
    for key, value in extreme_info.items():
        print(f"    {key}: {value}")


def test_edge_cases():
    """Test edge cases in candle aggregation and signal generation"""
    print("\n=== EDGE CASES TEST ===\n")

    # Case 1: Empty trades list
    print("--- Case 1: Empty trades ---")
    empty_candle = create_candle_from_trades([], 1000000000)
    print(f"  Result: {empty_candle}")
    assert empty_candle['volume'] == 0, "Empty trades should have zero volume"
    assert empty_candle['open'] == 0, "Empty trades should have zero OHLC"

    # Case 2: Single trade
    print("\n--- Case 2: Single trade ---")
    single_trade = [{'timestamp': 1000000000, 'price': 100.5, 'size': 10.0, 'side': 'Buy'}]
    single_candle = create_candle_from_trades(single_trade, 1000000000)
    print(f"  Result: {single_candle}")
    assert single_candle['open'] == single_candle['high'] == single_candle['low'] == single_candle['close']
    assert single_candle['volume'] == 10.0

    # Case 3: Trades with same price
    print("\n--- Case 3: Same price trades ---")
    same_price_trades = [
        {'timestamp': 1000000000, 'price': 100.0, 'size': 10.0, 'side': 'Buy'},
        {'timestamp': 1000000100, 'price': 100.0, 'size': 20.0, 'side': 'Sell'},
        {'timestamp': 1000000200, 'price': 100.0, 'size': 15.0, 'side': 'Buy'}
    ]
    same_price_candle = create_candle_from_trades(same_price_trades, 1000000000)
    print(f"  Result: {same_price_candle}")
    assert same_price_candle['high'] == same_price_candle['low'] == 100.0
    assert same_price_candle['volume'] == 45.0

    # Case 4: Very small volumes (fractional)
    print("\n--- Case 4: Fractional volumes ---")
    frac_trades = [
        {'timestamp': 1000000000, 'price': 0.00001, 'size': 0.001, 'side': 'Buy'},
        {'timestamp': 1000000100, 'price': 0.00002, 'size': 0.0005, 'side': 'Sell'}
    ]
    frac_candle = create_candle_from_trades(frac_trades, 1000000000)
    print(f"  Result: {frac_candle}")
    assert abs(frac_candle['volume'] - 0.0015) < 0.00001

    # Case 5: Signal with insufficient data
    print("\n--- Case 5: Insufficient data for signal ---")
    few_candles = [{'timestamp': i*10000, 'open': 100, 'high': 101, 'low': 99, 'close': 100, 'volume': 1000} for i in range(10)]
    signal, info = generate_signal(few_candles)
    print(f"  Signal: {signal}")
    print(f"  Validation error: {info.get('validation_error', 'None')}")
    assert signal == False, "Should not generate signal with <20 candles"

    # Case 6: Forward-fill candle (zero volume)
    print("\n--- Case 6: Forward-fill candle (zero volume) ---")
    ff_candles = [{'timestamp': i*10000, 'open': 100, 'high': 101, 'low': 99, 'close': 100, 'volume': 1000 if i < 19 else 0} for i in range(20)]
    signal, info = generate_signal(ff_candles)
    print(f"  Signal: {signal}")
    print(f"  Validation error: {info.get('validation_error', 'None')}")
    assert signal == False, "Should not generate signal for forward-fill candle"

    print("\n✅ All edge cases passed")


async def main():
    try:
        await test_signal_generation_live()
        print("\n" + "="*60 + "\n")

        test_signal_criteria_isolated()
        print("\n" + "="*60 + "\n")

        test_edge_cases()

    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n\nError during tests: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())