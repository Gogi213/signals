"""
Iteration 2 - Test #3: Validate H2.3
Find candles with 0ms interval

Expected: All intervals should be 10000ms
Reality: Logs show {10000, 0} → H2.3 VALID if duplicate candles found
"""
import json
import os
from collections import defaultdict

def find_zero_interval_candles():
    """Find pairs of candles with 0ms interval"""
    print("=" * 70)
    print("TEST #3: Zero-Interval Candle Detection")
    print("=" * 70)
    print()
    print("HYPOTHESIS H2.3: Some candles have 0ms interval (duplicate timestamps)")
    print()

    logs_file = 'logs/websocket.json'
    if not os.path.exists(logs_file):
        print(f"ERROR: {logs_file} not found")
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

    # Find zero intervals
    zero_intervals_found = []
    all_intervals = []

    for coin, candles in candles_by_coin.items():
        candles_sorted = sorted(candles, key=lambda x: x['timestamp'])

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
    unique_intervals = set(all_intervals)

    print(f"RESULTS:")
    print(f"  Total intervals checked: {len(all_intervals)}")
    print(f"  Unique interval values: {sorted(unique_intervals)}")
    print(f"  Zero-interval pairs found: {len(zero_intervals_found)}")
    print()

    # Show examples
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

    # Interval distribution
    print()
    print(f"Interval distribution:")
    interval_counts = defaultdict(int)
    for interval in all_intervals:
        interval_counts[interval] += 1

    for interval in sorted(interval_counts.keys())[:10]:
        count = interval_counts[interval]
        pct = (count / len(all_intervals)) * 100
        print(f"  {interval}ms: {count} ({pct:.1f}%)")

    # Validation
    print()
    print("=" * 70)
    print("HYPOTHESIS VALIDATION:")
    print("=" * 70)

    if len(zero_intervals_found) > 0:
        print(f"  [VALID] H2.3 VALID: Zero-interval candles detected")
        print(f"     Found: {len(zero_intervals_found)} pairs with 0ms interval")
        print(f"     Percentage: {len(zero_intervals_found)/len(all_intervals)*100:.2f}%")
        print(f"     Possible causes:")
        print(f"       - Finalization timer creating duplicate candles")
        print(f"       - Race condition in candle_locks")
        print(f"       - Logger logging same candle twice")
        h23_valid = True
    else:
        print(f"  [INVALID] H2.3 INVALID: All intervals are 10000ms")
        print(f"     No zero-interval pairs found")
        print(f"     Initial log analysis may have been incorrect")
        h23_valid = False

    # Save results
    results = {
        'test': 'zero_interval_detection',
        'h23_valid': h23_valid,
        'total_intervals': len(all_intervals),
        'unique_intervals': sorted(unique_intervals),
        'zero_interval_count': len(zero_intervals_found),
        'zero_interval_pct': len(zero_intervals_found)/len(all_intervals)*100 if all_intervals else 0,
        'examples': zero_intervals_found[:5]
    }

    with open('TESTS/iteration_2/test_03_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: test_03_results.json")

if __name__ == "__main__":
    find_zero_interval_candles()
