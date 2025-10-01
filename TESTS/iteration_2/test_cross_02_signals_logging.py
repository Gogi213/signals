"""
Cross-Audit #2 - Test C3.6: Signals Logging Validation

Check if signals.json contains proper passed/failed criteria or only warmup messages
"""
import json
import os

def validate_signals_logging():
    """Check signals.json content"""
    print("=" * 70)
    print("CROSS-AUDIT #2: Signals Logging Validation")
    print("=" * 70)
    print()
    print("HYPOTHESIS C3.6: signals.json only contains warmup messages, not real criteria")
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

    print(f"Total signals: {len(signals)}")
    print()

    # Categorize signals
    warmup_signals = []
    insufficient_data_signals = []
    real_signals = []

    for signal in signals:
        criteria = signal.get('criteria_details', {})

        # Check if warmup
        if isinstance(criteria, dict):
            val_err = criteria.get('validation_error', '')
            if 'Warmup' in val_err:
                warmup_signals.append(signal)
            elif 'Insufficient data' in val_err:
                insufficient_data_signals.append(signal)
            elif 'criteria_details' in criteria:
                # Has actual criteria_details sub-dict
                real_signals.append(signal)
            else:
                # No criteria_details, but no warmup either
                real_signals.append(signal)
        else:
            real_signals.append(signal)

    print(f"Categorization:")
    print(f"  Warmup signals: {len(warmup_signals)}")
    print(f"  Insufficient data: {len(insufficient_data_signals)}")
    print(f"  Real signals (with criteria): {len(real_signals)}")
    print()

    # Show examples
    if warmup_signals:
        print(f"Example warmup signal:")
        print(f"  {json.dumps(warmup_signals[0], indent=2)[:300]}...")
        print()

    if insufficient_data_signals:
        print(f"Example insufficient data signal:")
        print(f"  {json.dumps(insufficient_data_signals[0], indent=2)[:300]}...")
        print()

    if real_signals:
        print(f"Example real signal:")
        print(f"  {json.dumps(real_signals[0], indent=2)[:500]}...")
        print()
    else:
        print(f"NO REAL SIGNALS FOUND!")
        print()

    # Validation
    print("=" * 70)
    print("HYPOTHESIS VALIDATION")
    print("=" * 70)
    print()

    total_non_warmup = len(insufficient_data_signals) + len(real_signals)
    real_pct = (len(real_signals) / total_non_warmup * 100) if total_non_warmup > 0 else 0

    if len(real_signals) == 0:
        print(f"  [VALID] C3.6 VALID: No real signals with criteria in signals.json")
        print(f"     Only warmup ({len(warmup_signals)}) and insufficient data ({len(insufficient_data_signals)})")
        print(f"     Expected: Signals with passed/failed criteria like in console")
        print(f"     Problem: log_signal() not writing criteria_details properly")
        c36_valid = True
    elif real_pct < 50:
        print(f"  [VALID] C3.6 PARTIALLY VALID: Most signals lack criteria")
        print(f"     Real signals: {len(real_signals)} ({real_pct:.1f}%)")
        print(f"     Insufficient data: {len(insufficient_data_signals)}")
        c36_valid = True
    else:
        print(f"  [INVALID] C3.6 INVALID: Signals contain proper criteria")
        print(f"     Real signals: {len(real_signals)} ({real_pct:.1f}%)")
        c36_valid = False

    # Save results
    results = {
        'test': 'signals_logging_validation',
        'c36_valid': c36_valid,
        'total_signals': len(signals),
        'warmup_count': len(warmup_signals),
        'insufficient_data_count': len(insufficient_data_signals),
        'real_signals_count': len(real_signals),
        'real_signals_pct': real_pct
    }

    with open('TESTS/iteration_2/test_cross_02_signals_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: test_cross_02_signals_results.json")

if __name__ == "__main__":
    validate_signals_logging()
