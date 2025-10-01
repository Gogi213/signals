"""
Iteration 3 - Test #5: Validate H3.5
Test forward-fill behavior for low-activity coins

Expected: Forward-fill creates candles for low-activity coins
Reality: If excessive forward-fill → H3.5 VALID
"""
import json
import os
from collections import defaultdict

def test_forward_fill_behavior():
    """Test forward-fill behavior for low-activity coins"""
    print("=" * 70)
    print("TEST #5: Forward-Fill Behavior Validation")
    print("=" * 70)
    print()
    print("HYPOTHESIS H3.5: Forward-fill creates excessive candles for low-activity coins")
    print()
    print("VALIDATION:")
    print("  - Analyze websocket.json for zero-volume patterns")
    print("  - Expected: ~2.4% zero-volume from forward-fill")
    print("  - Reality: If much higher → H3.5 VALID")
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

    # Analyze zero-volume patterns
    total_candles = 0
    zero_volume_candles = 0
    consecutive_zeros = defaultdict(list)  # coin -> list of consecutive zero runs

    for coin, candles in candles_by_coin.items():
        candles_sorted = sorted(candles, key=lambda x: x['timestamp'])
        total_candles += len(candles_sorted)

        zero_run = 0
        for candle in candles_sorted:
            if candle['volume'] == 0:
                zero_volume_candles += 1
                zero_run += 1
            else:
                if zero_run > 0:
                    consecutive_zeros[coin].append(zero_run)
                zero_run = 0

        # Don't forget last run
        if zero_run > 0:
            consecutive_zeros[coin].append(zero_run)

    zero_pct = (zero_volume_candles / total_candles * 10) if total_candles > 0 else 0

    print(f"RESULTS:")
    print(f"  Total candles: {total_candles}")
    print(f"  Zero-volume: {zero_volume_candles} ({zero_pct:.1f}%)")
    print(f"  Expected: ~2.4% from previous audits")
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

        print(f"  Distribution (top 10):")
        for length in sorted(run_distribution.keys(), reverse=True)[:10]:
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

    # H3.5 is valid if zero-volume percentage is significantly higher than expected
    if zero_pct > 10:  # Significantly higher than expected ~2.4%
        print(f"  [VALID] H3.5 VALID: Excessive zero-volume candles detected")
        print(f"     Found: {zero_pct:.1f}% (expected ~2.4%)")
        print(f"     This suggests forward-fill creates too many candles for low-activity coins")
        print(f"     Confirms relationship with H3.2 (volume filter)")
        h35_valid = True
    else:
        print(f" [INVALID] H3.5 INVALID: Zero-volume within expected range")
        print(f"     Found: {zero_pct:.1f}% (expected ~2.4%)")
        h35_valid = False

    # Save results
    results = {
        'test': 'forward_fill_behavior',
        'h35_valid': h35_valid,
        'zero_volume_pct': zero_pct,
        'expected_pct': 2.4,
        'total_candles': total_candles,
        'zero_candles': zero_volume_candles,
        'consecutive_runs': {
            'total': len(all_runs) if all_runs else 0,
            'max': max(all_runs) if all_runs else 0,
            'avg': sum(all_runs) / len(all_runs) if all_runs else 0
        },
        'top_3_problematic_coins': [
            {'coin': coin, 'pct': coin_zero_pcts[coin]} 
            for coin in sorted(coin_zero_pcts, key=coin_zero_pcts.get, reverse=True)[:3]
        ]
    }

    with open('TESTS/kilo/test_05_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: test_05_results.json")

if __name__ == "__main__":
    test_forward_fill_behavior()