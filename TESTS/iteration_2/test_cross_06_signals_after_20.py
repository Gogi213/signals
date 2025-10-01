"""
Test C6.6: Do signals.json logs STOP after 20 candles?

Run for 5 minutes (30 candles per coin) and check if signals.json contains
candles 20+
"""
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from main import main

async def test_signals_after_20():
    """Run main() for 5 minutes"""
    print("=" * 70)
    print("TEST C6.6: Signals After 20 Candles")
    print("=" * 70)
    print()
    print("Running for 5 minutes (300s = 30 candles)")
    print("Checking if signals.json contains candles 20+")
    print()

    start_time = time.time()

    try:
        await asyncio.wait_for(main(), timeout=300.0)
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        print(f"\nTimeout after {elapsed:.1f}s")
    except KeyboardInterrupt:
        print("\nInterrupted")

    # Analyze signals.json
    print()
    print("=" * 70)
    print("ANALYZING signals.json")
    print("=" * 70)

    import json
    signals_file = 'logs/signals.json'

    if not os.path.exists(signals_file):
        print("ERROR: signals.json not found")
        return

    signals = []
    with open(signals_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                signals.append(json.loads(line))
            except:
                pass

    print(f"\nTotal signals: {len(signals)}")

    # Categorize by candle_count
    by_candles = {}
    for signal in signals:
        criteria = signal.get('criteria_details', {})
        candle_count = criteria.get('candle_count', 0)
        if candle_count not in by_candles:
            by_candles[candle_count] = []
        by_candles[candle_count].append(signal)

    print(f"\nSignals by candle count:")
    for count in sorted(by_candles.keys())[:20]:
        signals_at_count = by_candles[count]
        has_criteria = sum(1 for s in signals_at_count
                          if s.get('criteria_details', {}).get('criteria_details', {}))
        print(f"  {count} candles: {len(signals_at_count)} signals "
              f"({has_criteria} with criteria_details)")

    # Check if any signal has candle_count >= 20 with criteria_details
    signals_20plus = [s for s in signals
                      if s.get('criteria_details', {}).get('candle_count', 0) >= 20]

    signals_20plus_with_criteria = [s for s in signals_20plus
                                    if s.get('criteria_details', {}).get('criteria_details', {})]

    print(f"\nSignals with 20+ candles: {len(signals_20plus)}")
    print(f"  With criteria_details: {len(signals_20plus_with_criteria)}")

    if signals_20plus_with_criteria:
        print(f"\n  Example signal with criteria:")
        example = signals_20plus_with_criteria[0]
        print(f"    Coin: {example.get('coin')}")
        print(f"    Candles: {example['criteria_details']['candle_count']}")
        criteria_det = example['criteria_details']['criteria_details']
        print(f"    Criteria: {list(criteria_det.keys())}")

    # Validation
    print()
    print("=" * 70)
    print("HYPOTHESIS VALIDATION")
    print("=" * 70)

    if len(signals_20plus) == 0:
        print(f"\n[UNCERTAIN] C6.6: No signals with 20+ candles found")
        print(f"  Test may not have run long enough")
        c66_valid = None
    elif len(signals_20plus_with_criteria) > 0:
        print(f"\n[INVALID] C6.6 INVALID: Signals with criteria found after 20 candles")
        print(f"  Found {len(signals_20plus_with_criteria)} signals with full criteria")
        c66_valid = False
    else:
        print(f"\n[VALID] C6.6 VALID: Signals STOP logging criteria after 20 candles")
        print(f"  Found {len(signals_20plus)} signals with 20+ candles")
        print(f"  BUT 0 have criteria_details!")
        c66_valid = True

    # Save results
    results = {
        'test': 'signals_after_20_candles',
        'c66_valid': c66_valid,
        'total_signals': len(signals),
        'signals_20plus': len(signals_20plus),
        'signals_20plus_with_criteria': len(signals_20plus_with_criteria)
    }

    with open('TESTS/iteration_2/test_cross_06_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: test_cross_06_results.json")

if __name__ == "__main__":
    asyncio.run(test_signals_after_20())
