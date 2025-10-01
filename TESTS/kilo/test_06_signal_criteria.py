"""
Iteration 3 - Test #6: Validate H3.6
Test signal criteria strictness

Expected: Some signals should be generated
Reality: If 0 TRUE signals → H3.6 VALID
"""
import json
import os
from collections import defaultdict

def test_signal_criteria():
    """Test signal criteria effectiveness"""
    print("=" * 70)
    print("TEST #6: Signal Criteria Validation")
    print("=" * 70)
    print()
    print("HYPOTHESIS H3.6: Signal criteria too strict (0 TRUE signals)")
    print()
    print("VALIDATION:")
    print("  - Analyze signals.json for TRUE/FALSE distribution")
    print("  - Expected: Some TRUE signals if criteria appropriate")
    print("  - Reality: If 0 TRUE signals → H3.6 VALID")
    print()

    logs_file = 'logs/signals.json'
    if not os.path.exists(logs_file):
        print(f"ERROR: {logs_file} not found")
        print("Need to run application to generate signal logs")
        return

    # Load signal logs
    signal_logs = []

    with open(logs_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                log = json.loads(line)
                signal_logs.append(log)
            except:
                pass

    print(f"Loaded {len(signal_logs)} signal logs")
    print()

    # Analyze signals
    true_signals = [l for l in signal_logs if l.get('signal_type') == 'true']
    false_signals = [l for l in signal_logs if l.get('signal_type') == 'false']

    print(f"Signal distribution:")
    print(f"  TRUE signals: {len(true_signals)}")
    print(f"  FALSE signals: {len(false_signals)}")
    print()

    # Analyze criteria failures if no true signals
    criteria_failures = defaultdict(int)
    criteria_details = []

    for log in false_signals:
        criteria = log.get('criteria_details', {})
        if isinstance(criteria, dict):
            for crit_name, details in criteria.items():
                if isinstance(details, dict) and not details.get('passed', True):
                    criteria_failures[crit_name] += 1
                    criteria_details.append({
                        'coin': log.get('coin'),
                        'criterion': crit_name,
                        'current': details.get('current'),
                        'threshold': details.get('threshold'),
                        'passed': details.get('passed')
                    })

    print(f"Criteria failure counts:")
    for crit, count in sorted(criteria_failures.items(), key=lambda x: -x[1]):
        print(f" {crit}: {count}")

    # Validation
    print()
    print("=" * 70)
    print("HYPOTHESIS VALIDATION:")
    print("=" * 70)

    if len(true_signals) == 0 and len(signal_logs) > 0:
        print(f"  [VALID] H3.6 VALID: No TRUE signals generated")
        print(f"     TRUE: {len(true_signals)}, FALSE: {len(false_signals)}")
        print(f"     This suggests criteria may be too strict")
        print(f"     Or market conditions don't meet criteria")
        print(f"     Most failed criteria: {sorted(criteria_failures.items(), key=lambda x: -x[1])[0] if criteria_failures else 'None'}")
        h36_valid = True
    elif len(true_signals) > 0:
        print(f" [INVALID] H3.6 INVALID: TRUE signals were generated")
        print(f"     TRUE: {len(true_signals)}, FALSE: {len(false_signals)}")
        print(f"     Criteria are appropriately strict")
        h36_valid = False
    else:
        print(f" [UNCERTAIN] H3.6 UNCERTAIN: No signal logs found")
        h36_valid = False

    # Additional analysis: Check criteria values
    if criteria_details:
        print(f"\nSample criteria details:")
        for detail in criteria_details[:5]:  # Show first 5
            print(f"  {detail['coin']}: {detail['criterion']} = {detail['current']} vs {detail['threshold']} (passed: {detail['passed']})")

    # Save results
    results = {
        'test': 'signal_criteria',
        'h36_valid': h36_valid,
        'true_signals': len(true_signals),
        'false_signals': len(false_signals),
        'total_signals': len(signal_logs),
        'criteria_failures': dict(criteria_failures),
        'sample_criteria_details': criteria_details[:10]
    }

    with open('TESTS/kilo/test_06_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: test_06_results.json")

if __name__ == "__main__":
    test_signal_criteria()