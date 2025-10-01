"""
Iteration 3 - Test #4: Validate H3.4
Test async logging reordering issue

Expected: Candles should be logged in chronological order
Reality: If duplicate timestamps found → H3.4 VALID
"""
import json
import os
from collections import defaultdict

def test_async_logging_order():
    """Test for async logging reordering by checking timestamp patterns"""
    print("=" * 70)
    print("TEST #4: Async Logging Reordering Validation")
    print("=" * 70)
    print()
    print("HYPOTHESIS H3.4: Async logging queue reorders candles")
    print()
    print("VALIDATION:")
    print("  - Analyze websocket.json for timestamp patterns")
    print(" - Expected: Sequential timestamps (10s intervals)")
    print("  - Reality: If duplicate timestamps found → H3.4 VALID")
    print()

    logs_file = 'logs/websocket.json'
    if not os.path.exists(logs_file):
        print(f"ERROR: {logs_file} not found")
        print("Need to run collect_fresh_logs.py first")
        return

    # Load candles
    candles_by_coin = defaultdict(list)

    with open(logs_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                log = json.loads(line)
                if 'candle_data' in log:
                    coin = log.get('coin')
                    candle = log.get('candle_data')
                    if coin and candle:
                        candles_by_coin[coin].append(candle)
            except:
                pass

    print(f"Loaded {len(candles_by_coin)} coins")
    print()

    # Find zero intervals (duplicate timestamps)
    zero_intervals_found = []
    all_intervals = []
    total_candles = 0

    for coin, candles in candles_by_coin.items():
        candles_sorted = sorted(candles, key=lambda x: x['timestamp'])
        total_candles += len(candles_sorted)

        for i in range(1, len(candles_sorted)):
            prev_candle = candles_sorted[i-1]
            curr_candle = candles_sorted[i]

            interval = curr_candle['timestamp'] - prev_candle['timestamp']
            all_intervals.append(interval)

            if interval == 0:
                zero_intervals_found.append({
                    'coin': coin,
                    'index': i,
                    'prev_candle': prev_candle,
                    'curr_candle': curr_candle,
                    'timestamp': curr_candle['timestamp']
                })

    # Results
    unique_intervals = set(all_intervals) if all_intervals else set()

    print(f"RESULTS:")
    print(f"  Total candles analyzed: {total_candles}")
    print(f"  Total intervals checked: {len(all_intervals)}")
    print(f"  Unique interval values: {sorted(unique_intervals)}")
    print(f"  Zero-interval pairs found: {len(zero_intervals_found)}")
    print()

    # Show examples of zero-interval pairs
    if zero_intervals_found:
        print(f"Examples of zero-interval pairs (showing first 5):")
        for item in zero_intervals_found[:5]:
            print(f"\n  Coin: {item['coin']}")
            print(f"  Timestamp: {item['timestamp']}")
            print(f"  Prev candle: O:{item['prev_candle']['open']} H:{item['prev_candle']['high']} "
                  f"L:{item['prev_candle']['low']} C:{item['prev_candle']['close']} V:{item['prev_candle']['volume']}")
            print(f"  Curr candle: O:{item['curr_candle']['open']} H:{item['curr_candle']['high']} "
                  f"L:{item['curr_candle']['low']} C:{item['curr_candle']['close']} V:{item['curr_candle']['volume']}")

            # Check if they are exact duplicates
            prev = item['prev_candle']
            curr = item['curr_candle']
            is_duplicate = (prev['open'] == curr['open'] and
                          prev['high'] == curr['high'] and
                          prev['low'] == curr['low'] and
                          prev['close'] == curr['close'] and
                          prev['volume'] == curr['volume'])
            print(f"  Exact duplicate: {is_duplicate}")

    # Interval distribution analysis
    if all_intervals:
        from collections import Counter
        interval_counts = Counter(all_intervals)
        
        print(f"\nTop 10 interval distributions:")
        for interval in sorted(interval_counts.keys(), key=lambda x: -interval_counts[x])[:10]:
            count = interval_counts[interval]
            pct = (count / len(all_intervals)) * 10
            print(f"  {interval}ms: {count} ({pct:.1f}%)")

    # Validation
    print()
    print("=" * 70)
    print("HYPOTHESIS VALIDATION:")
    print("=" * 70)

    if len(zero_intervals_found) > 0:
        zero_pct = len(zero_intervals_found)/len(all_intervals)*100 if all_intervals else 0
        print(f"  [VALID] H3.4 VALID: Zero-interval candles detected")
        print(f"     Found: {len(zero_intervals_found)} pairs with 0ms interval")
        print(f"     Percentage: {zero_pct:.2f}%")
        print(f"     This suggests async logging may be reordering candles")
        h34_valid = True
    else:
        print(f"  [INVALID] H3.4 INVALID: No zero-interval pairs found")
        print(f"     All intervals are properly sequential")
        print(f"     Async logging appears to preserve order")
        h34_valid = False

    # Additional analysis: Look for out-of-order timestamps (another sign of reordering)
    out_of_order_count = 0
    for coin, candles in candles_by_coin.items():
        # Original order from file vs sorted order
        original_timestamps = [c['timestamp'] for c in candles]
        sorted_timestamps = sorted(original_timestamps)
        
        if original_timestamps != sorted_timestamps:
            # Count how many are out of order
            for i in range(len(original_timestamps)-1):
                if original_timestamps[i] > original_timestamps[i+1]:
                    out_of_order_count += 1

    if out_of_order_count > 0:
        print(f"  Additional finding: {out_of_order_count} out-of-order timestamps detected")
        print(f"  This further supports async logging reordering hypothesis")

    # Save results
    results = {
        'test': 'async_logging_reordering',
        'h34_valid': h34_valid,
        'total_candles': total_candles,
        'total_intervals': len(all_intervals),
        'unique_intervals': sorted(unique_intervals),
        'zero_interval_count': len(zero_intervals_found),
        'zero_interval_pct': len(zero_intervals_found)/len(all_intervals)*100 if all_intervals else 0,
        'out_of_order_count': out_of_order_count,
        'examples': zero_intervals_found[:5]
    }

    with open('TESTS/kilo/test_04_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: test_04_results.json")

if __name__ == "__main__":
    test_async_logging_order()