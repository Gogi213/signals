"""
Iteration 2 - Test #4: Validate H2.4
Test warmup completion logic

Expected: Warmup logs from 1/10 to 10/10
Reality: Only saw "1/10" in logs → H2.4 VALID if warmup completes too early
"""
import asyncio
import sys
import os
import time
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from main import main

async def test_warmup_completion():
    """Monitor warmup completion timing"""
    print("=" * 70)
    print("TEST #4: Warmup Completion Logic")
    print("=" * 70)
    print()
    print("HYPOTHESIS H2.4: Warmup completes at 1/10 instead of 10/10")
    print()
    print("VALIDATION:")
    print("  - Run for 2 minutes")
    print("  - Parse logs to find warmup progress")
    print("  - Find when warmup_complete becomes True")
    print("  - Expected: Should complete after 10 candles (100s)")
    print()

    # Clear old logs
    logs_dir = 'logs'
    for f in ['system.json', 'signals.json']:
        filepath = os.path.join(logs_dir, f)
        if os.path.exists(filepath):
            os.remove(filepath)

    print(f"Starting 2-minute test run...")
    print()

    start_time = time.time()

    try:
        # Run for 2 minutes
        await asyncio.wait_for(main(), timeout=120.0)
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        print(f"\nTimeout reached after {elapsed:.1f}s")
    except KeyboardInterrupt:
        print(f"\nTest interrupted")
    except Exception as e:
        print(f"\nError: {e}")

    # Analyze logs
    print()
    print("=" * 70)
    print("ANALYZING LOGS")
    print("=" * 70)

    # Parse system.json for warmup progression
    system_logs = []
    system_file = os.path.join(logs_dir, 'system.json')
    if os.path.exists(system_file):
        with open(system_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    log = json.loads(line)
                    system_logs.append(log)
                except:
                    pass

    warmup_logs = [l for l in system_logs if 'Warmup' in l.get('message', '')]

    print(f"\nSystem logs: {len(system_logs)}")
    print(f"Warmup logs: {len(warmup_logs)}")
    print()

    if warmup_logs:
        print(f"Warmup progression:")
        for log in warmup_logs:
            print(f"  {log['message']}")
    else:
        print(f"No warmup logs found!")

    # Parse signals.json to find when signals started
    signals_logs = []
    signals_file = os.path.join(logs_dir, 'signals.json')
    if os.path.exists(signals_file):
        with open(signals_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    log = json.loads(line)
                    signals_logs.append(log)
                except:
                    pass

    print()
    print(f"Signal logs: {len(signals_logs)}")

    # Find first signal log (indicates warmup complete)
    first_signal_time = None
    if signals_logs:
        first_signal_time = signals_logs[0].get('timestamp')
        print(f"First signal logged at: {first_signal_time}")

    # Parse websocket.json to count candles before signals
    candles_before_signals = []
    websocket_file = os.path.join(logs_dir, 'websocket.json')
    if os.path.exists(websocket_file) and first_signal_time:
        with open(websocket_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    log = json.loads(line)
                    if 'candle_data' in log:
                        log_time = log.get('timestamp')
                        if log_time and log_time < first_signal_time:
                            candles_before_signals.append(log)
                except:
                    pass

        # Count candles per coin before signals
        from collections import defaultdict
        candles_per_coin = defaultdict(int)
        for log in candles_before_signals:
            coin = log.get('coin')
            if coin:
                candles_per_coin[coin] += 1

        if candles_per_coin:
            min_candles = min(candles_per_coin.values())
            max_candles = max(candles_per_coin.values())
            avg_candles = sum(candles_per_coin.values()) / len(candles_per_coin)

            print(f"\nCandles before first signal:")
            print(f"  Min per coin: {min_candles}")
            print(f"  Max per coin: {max_candles}")
            print(f"  Avg per coin: {avg_candles:.1f}")
            print(f"  Expected: 10 (WARMUP_INTERVALS)")

    # Validation
    print()
    print("=" * 70)
    print("HYPOTHESIS VALIDATION:")
    print("=" * 70)

    # Check if warmup logs stopped early
    expected_warmup_logs = 1  # Should see "1/10" only if logging every 10
    # But main.py logs every 10 intervals OR on first candle
    # So we should see 1/10 (first), maybe 10/10 (final) if it completes

    h24_valid = False
    conclusion = ""

    if not warmup_logs:
        print(f"  [UNCERTAIN] H2.4: No warmup logs found")
        print(f"     Cannot determine if warmup logic is working")
        conclusion = "no_logs"
    elif len(warmup_logs) == 1:
        print(f"  [VALID] H2.4 VALID: Only 1 warmup log found")
        print(f"     Expected: Multiple logs showing progression to 10/10")
        print(f"     Found: {warmup_logs[0]['message']}")
        print(f"     Possible causes:")
        print(f"       - Warmup completes too quickly (race condition)")
        print(f"       - Logging stopped prematurely")
        print(f"       - warmup_complete flag set incorrectly")
        h24_valid = True
        conclusion = "single_log"
    else:
        print(f"  [INVALID] H2.4 INVALID: Multiple warmup logs found")
        print(f"     Warmup appears to progress normally")
        print(f"     Logs: {[l['message'] for l in warmup_logs]}")
        conclusion = "multiple_logs"

    # Save results
    results = {
        'test': 'warmup_completion',
        'h24_valid': h24_valid,
        'warmup_log_count': len(warmup_logs),
        'warmup_messages': [l['message'] for l in warmup_logs],
        'signal_log_count': len(signals_logs),
        'candles_before_signals': len(candles_before_signals),
        'conclusion': conclusion
    }

    with open('TESTS/iteration_2/test_04_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: test_04_results.json")

if __name__ == "__main__":
    asyncio.run(test_warmup_completion())
