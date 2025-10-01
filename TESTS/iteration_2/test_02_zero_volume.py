"""
Iteration 2 - Test #2: Validate H2.2
Analyze zero-volume candle patterns

Expected: ~2.4% zero-volume (forward-fill)
Reality: 46.2% from logs → H2.2 VALID if pattern is wrong
"""
import json
import os
from collections import defaultdict

def analyze_zero_volume_patterns():
    """Analyze zero-volume candle distribution"""
    print("=" * 70)
    print("TEST #2: Zero-Volume Candle Pattern Analysis")
    print("=" * 70)
    print()
    print("HYPOTHESIS H2.2: 46.2% zero-volume vs expected 2.4%")
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

    # Analyze patterns
    total_candles = 0
    total_zero_volume = 0
    consecutive_zeros = defaultdict(list)  # coin -> list of consecutive zero runs

    for coin, candles in candles_by_coin.items():
        candles_sorted = sorted(candles, key=lambda x: x['timestamp'])
        total_candles += len(candles_sorted)

        zero_run = 0
        for candle in candles_sorted:
            if candle['volume'] == 0:
                total_zero_volume += 1
                zero_run += 1
            else:
                if zero_run > 0:
                    consecutive_zeros[coin].append(zero_run)
                zero_run = 0

        # Don't forget last run
        if zero_run > 0:
            consecutive_zeros[coin].append(zero_run)

    zero_pct = (total_zero_volume / total_candles * 100) if total_candles > 0 else 0

    print(f"RESULTS:")
    print(f"  Total candles: {total_candles}")
    print(f"  Zero-volume: {total_zero_volume} ({zero_pct:.1f}%)")
    print(f"  Expected: ~2.4%")
    print()

    # Analyze consecutive runs
    all_runs = []
    for runs in consecutive_zeros.values():
        all_runs.extend(runs)

    if all_runs:
        max_run = max(all_runs)
        avg_run = sum(all_runs) / len(all_runs)
        total_runs = len(all_runs)

        print(f"Zero-Volume Run Analysis:")
        print(f"  Total runs: {total_runs}")
        print(f"  Max consecutive: {max_run}")
        print(f"  Average consecutive: {avg_run:.1f}")
        print()

        # Show distribution
        run_distribution = defaultdict(int)
        for run in all_runs:
            run_distribution[run] += 1

        print(f"  Distribution:")
        for length in sorted(run_distribution.keys())[:10]:
            count = run_distribution[length]
            print(f"    {length} consecutive: {count} times")

    # Sample analysis - show 3 coins with most zero-volume
    print()
    print(f"Top 3 coins with most zero-volume:")

    coin_zero_pcts = {}
    for coin, candles in candles_by_coin.items():
        zero_count = sum(1 for c in candles if c['volume'] == 0)
        pct = (zero_count / len(candles)) * 100
        coin_zero_pcts[coin] = pct

    for coin in sorted(coin_zero_pcts, key=coin_zero_pcts.get, reverse=True)[:3]:
        pct = coin_zero_pcts[coin]
        candles = candles_by_coin[coin]
        print(f"  {coin}: {pct:.1f}% zero-volume ({sum(1 for c in candles if c['volume'] == 0)}/{len(candles)})")

    # Validation
    print()
    print("=" * 70)
    print("HYPOTHESIS VALIDATION:")
    print("=" * 70)

    if zero_pct > 10:  # Threshold - significantly higher than 2.4%
        print(f"  [VALID] H2.2 VALID: Excessive zero-volume candles")
        print(f"     Found: {zero_pct:.1f}% (expected ~2.4%)")
        print(f"     Possible causes:")
        print(f"       - Gap-filling creating too many forward-fill candles")
        print(f"       - Low activity coins included in monitoring")
        print(f"       - Timer finalization creating candles without trades")
        h22_valid = True
    else:
        print(f"  [INVALID] H2.2 INVALID: Zero-volume within acceptable range")
        print(f"     Found: {zero_pct:.1f}% (expected ~2.4%)")
        h22_valid = False

    # Save results
    results = {
        'test': 'zero_volume_patterns',
        'h22_valid': h22_valid,
        'zero_volume_pct': zero_pct,
        'expected_pct': 2.4,
        'total_candles': total_candles,
        'zero_candles': total_zero_volume,
        'consecutive_runs': {
            'total': len(all_runs) if all_runs else 0,
            'max': max(all_runs) if all_runs else 0,
            'avg': sum(all_runs) / len(all_runs) if all_runs else 0
        }
    }

    with open('TESTS/iteration_2/test_02_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: test_02_results.json")

if __name__ == "__main__":
    analyze_zero_volume_patterns()
