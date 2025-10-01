"""
RE-VALIDATION C2.1: FARTCOIN 51 consecutive zeros is IMPOSSIBLE

User observation: $319M turnover24h coin CANNOT have 51 dead intervals (510s)
Hypothesis: BUG in code, not low activity
"""
import json
import os
from collections import defaultdict

def analyze_fartcoin_zeros():
    """Deep dive into FARTCOIN zero-volume pattern"""
    print("=" * 70)
    print("RE-VALIDATION: FARTCOIN 51 Consecutive Zeros")
    print("=" * 70)
    print()

    logs_file = 'logs/websocket.json'
    if not os.path.exists(logs_file):
        print("ERROR: websocket.json not found")
        return

    # Load all FARTCOIN candles
    fartcoin_candles = []

    with open(logs_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                log = json.loads(line)
                if log.get('coin') == 'FARTCOINUSDT' and 'candle_data' in log:
                    fartcoin_candles.append(log['candle_data'])
            except:
                pass

    if not fartcoin_candles:
        print("ERROR: No FARTCOIN candles found")
        return

    # Sort by timestamp
    fartcoin_candles = sorted(fartcoin_candles, key=lambda x: x['timestamp'])

    print(f"Total FARTCOIN candles: {len(fartcoin_candles)}")
    print()

    # Analyze zero-volume runs
    zero_runs = []
    current_run = []

    for i, candle in enumerate(fartcoin_candles):
        if candle['volume'] == 0:
            current_run.append({
                'index': i,
                'timestamp': candle['timestamp'],
                'candle': candle
            })
        else:
            if len(current_run) > 0:
                zero_runs.append(current_run)
                current_run = []

    if len(current_run) > 0:
        zero_runs.append(current_run)

    print(f"Zero-volume runs found: {len(zero_runs)}")
    print()

    # Find longest run
    longest_run = max(zero_runs, key=len) if zero_runs else []

    if longest_run:
        print(f"LONGEST RUN: {len(longest_run)} consecutive zeros")
        print(f"Duration: {len(longest_run) * 10} seconds")
        print()

        # Show details of longest run
        print(f"Details of longest run:")
        for i, item in enumerate(longest_run[:5]):  # First 5
            candle = item['candle']
            from datetime import datetime
            ts = datetime.fromtimestamp(candle['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
            print(f"  [{i+1}] {ts} | O:{candle['open']} H:{candle['high']} L:{candle['low']} C:{candle['close']} V:{candle['volume']}")

        if len(longest_run) > 5:
            print(f"  ... ({len(longest_run) - 5} more)")

        print()

        # CRITICAL CHECK: Are these REAL zeros or DUPLICATE timestamps?
        timestamps = [item['timestamp'] for item in longest_run]
        unique_timestamps = set(timestamps)

        print(f"CRITICAL CHECK:")
        print(f"  Total candles in run: {len(longest_run)}")
        print(f"  Unique timestamps: {len(unique_timestamps)}")

        if len(unique_timestamps) < len(longest_run):
            print(f"  [DUPLICATE TIMESTAMPS DETECTED!]")
            print(f"  This is NOT 51 dead intervals, but DUPLICATE LOGGING!")

            # Show duplicates
            from collections import Counter
            ts_counts = Counter(timestamps)
            duplicates = {ts: count for ts, count in ts_counts.items() if count > 1}

            print(f"\n  Duplicate timestamps:")
            for ts, count in list(duplicates.items())[:3]:
                from datetime import datetime
                ts_str = datetime.fromtimestamp(ts / 1000).strftime('%H:%M:%S')
                print(f"    {ts_str}: {count} times")
        else:
            print(f"  [NO DUPLICATES]")
            print(f"  These are REAL consecutive dead intervals")

    # Check if zero-volume candles have SAME price (forward-fill indicator)
    print()
    print("FORWARD-FILL CHECK:")

    if longest_run:
        prices = [(c['candle']['open'], c['candle']['high'], c['candle']['low'], c['candle']['close']) for c in longest_run]
        unique_prices = set(prices)

        print(f"  Unique OHLC combinations: {len(unique_prices)}")

        if len(unique_prices) == 1:
            print(f"  [FORWARD-FILL CONFIRMED]")
            print(f"  All zeros have SAME price: {prices[0]}")
            print(f"  This means NO TRADES for {len(longest_run) * 10}s")
        else:
            print(f"  [NOT FORWARD-FILL]")
            print(f"  Prices vary: {list(unique_prices)[:3]}")

    # NEW HYPOTHESIS: Check if zeros are at SPECIFIC TIMES
    print()
    print("TIMING PATTERN CHECK:")

    all_zero_candles = []
    for candle in fartcoin_candles:
        if candle['volume'] == 0:
            all_zero_candles.append(candle)

    # Group by hour
    from datetime import datetime
    hours = defaultdict(int)
    for candle in all_zero_candles:
        hour = datetime.fromtimestamp(candle['timestamp'] / 1000).hour
        hours[hour] += 1

    print(f"  Zero-volume candles by hour (UTC):")
    for hour in sorted(hours.keys()):
        print(f"    {hour:02d}:00 - {hours[hour]} zeros")

    # VALIDATION
    print()
    print("=" * 70)
    print("HYPOTHESIS VALIDATION")
    print("=" * 70)
    print()

    if longest_run:
        timestamps = [item['timestamp'] for item in longest_run]
        unique_timestamps = set(timestamps)

        if len(unique_timestamps) < len(longest_run):
            print(f"[HYPOTHESIS] C2.1 is WRONG!")
            print(f"  51 zeros are NOT dead intervals")
            print(f"  They are DUPLICATE LOGGING (queue reordering)")
            print(f"  Real problem: C3.3 (queue), not C2.1 (volume filter)")
            c21_revalidated = False
            real_cause = "C3.3 queue reordering creates fake consecutive zeros"
        else:
            prices = [(c['candle']['open'], c['candle']['high'], c['candle']['low'], c['candle']['close']) for c in longest_run]
            unique_prices = set(prices)

            if len(unique_prices) == 1:
                print(f"[HYPOTHESIS] C2.1 may be partially correct")
                print(f"  51 zeros ARE real dead intervals (forward-fill)")
                print(f"  BUT User is right: $319M coin shouldn't be dead for 510s")
                print(f"  POSSIBLE CAUSES:")
                print(f"    1. API returns stale data")
                print(f"    2. WebSocket connection dropped, reconnected")
                print(f"    3. Bybit API issue at that specific time")
                print(f"    4. Bug in finalization timer")
                c21_revalidated = "uncertain"
                real_cause = "Need to check WebSocket reconnections and API health"
            else:
                print(f"[HYPOTHESIS] Unknown issue")
                print(f"  Different prices but volume=0?")
                print(f"  This shouldn't happen in forward-fill")
                c21_revalidated = None
                real_cause = "Unknown"

    # Save results
    results = {
        'test': 'fartcoin_revalidation',
        'c21_revalidated': c21_revalidated,
        'real_cause': real_cause,
        'longest_run': len(longest_run) if longest_run else 0,
        'unique_timestamps': len(unique_timestamps) if longest_run else 0,
        'total_candles': len(fartcoin_candles),
        'zero_candles': len(all_zero_candles)
    }

    with open('TESTS/iteration_2/REVALIDATE_C2_1_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: REVALIDATE_C2_1_results.json")

if __name__ == "__main__":
    analyze_fartcoin_zeros()
