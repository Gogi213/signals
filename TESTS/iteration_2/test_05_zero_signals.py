"""
Test H2.7 - Zero TRUE Signals Analysis

Check why 0 TRUE signals in 8148 checks
"""
import json
import os
from collections import defaultdict

def analyze_zero_signals():
    """Analyze criteria for zero TRUE signals"""
    print("=" * 70)
    print("TEST #5: Zero TRUE Signals Analysis")
    print("=" * 70)
    print()
    print("HYPOTHESIS H2.7: 0 TRUE signals in 8148 checks is suspicious")
    print()

    signals_file = 'logs/signals.json'
    if not os.path.exists(signals_file):
        print(f"ERROR: {signals_file} not found")
        return

    # Load signals
    signals = []
    with open(signals_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                signals.append(json.loads(line))
            except:
                pass

    print(f"Total signal logs: {len(signals)}")
    print()

    # Count by type
    true_signals = [s for s in signals if s.get('signal_type') == 'true']
    false_signals = [s for s in signals if s.get('signal_type') == 'false']

    print(f"TRUE signals: {len(true_signals)}")
    print(f"FALSE signals: {len(false_signals)}")
    print()

    # Analyze criteria failures
    criteria_failures = defaultdict(int)
    criteria_details = defaultdict(list)

    for signal in false_signals[:100]:  # Sample first 100
        criteria = signal.get('criteria_details', {})
        if isinstance(criteria, dict):
            for crit_name, details in criteria.items():
                if isinstance(details, dict):
                    passed = details.get('passed', True)
                    if not passed:
                        criteria_failures[crit_name] += 1
                        criteria_details[crit_name].append({
                            'current': details.get('current'),
                            'threshold': details.get('threshold')
                        })

    print(f"Criteria failure analysis (first 100 signals):")
    for crit, count in sorted(criteria_failures.items(), key=lambda x: -x[1]):
        print(f"  {crit}: {count} failures")

        # Show sample values
        samples = criteria_details[crit][:3]
        for i, sample in enumerate(samples, 1):
            print(f"    Example {i}: current={sample['current']} vs threshold={sample['threshold']}")

    print()

    # Check if ANY signal was close to passing
    close_to_passing = 0
    for signal in false_signals[:100]:
        criteria = signal.get('criteria_details', {})
        if isinstance(criteria, dict):
            passed_count = sum(1 for d in criteria.values() if isinstance(d, dict) and d.get('passed', False))
            total_count = len(criteria)

            if passed_count >= total_count - 1:  # Failed only 1 criterion
                close_to_passing += 1

    print(f"Signals close to passing (failed only 1 criterion): {close_to_passing}/100")
    print()

    # Validation
    print("=" * 70)
    print("HYPOTHESIS VALIDATION:")
    print("=" * 70)

    if len(true_signals) == 0:
        # Check if criteria are too strict
        if criteria_failures:
            most_failed = max(criteria_failures, key=criteria_failures.get)
            failure_rate = criteria_failures[most_failed] / len(false_signals[:100])

            if failure_rate > 0.9:  # >90% fail on same criterion
                print(f"  [INVALID] H2.7 INVALID: Criteria are too strict, not suspicious")
                print(f"     Most failed criterion: {most_failed} ({failure_rate*100:.0f}% failure rate)")
                print(f"     This is expected behavior - market conditions don't match criteria")
                h27_valid = False
            else:
                print(f"  [VALID] H2.7 VALID: Zero signals is suspicious")
                print(f"     Criteria failures distributed: {dict(criteria_failures)}")
                print(f"     May indicate logic error")
                h27_valid = True
        else:
            print(f"  [UNCERTAIN] H2.7: No criteria details available")
            h27_valid = None
    else:
        print(f"  [INVALID] H2.7 INVALID: Found {len(true_signals)} TRUE signals")
        h27_valid = False

    # Save results
    results = {
        'test': 'zero_signals_analysis',
        'h27_valid': h27_valid,
        'total_signals': len(signals),
        'true_count': len(true_signals),
        'false_count': len(false_signals),
        'criteria_failures': dict(criteria_failures),
        'close_to_passing': close_to_passing
    }

    with open('TESTS/iteration_2/test_05_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: test_05_results.json")

if __name__ == "__main__":
    analyze_zero_signals()
