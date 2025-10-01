"""
Iteration 3 - Test #3: Validate H3.3
Test warmup logging interval issue

Expected: Warmup logs should show progression from 1/10 to 10/10
Reality: If only "1/10" appears → H3.3 VALID
"""
import asyncio
import sys
import os
import time
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from main import main

async def test_warmup_logging():
    """Test warmup logging behavior"""
    print("=" * 70)
    print("TEST #3: Warmup Logging Interval Validation")
    print("=" * 70)
    print()
    print("HYPOTHESIS H3.3: Warmup logging interval condition is too large")
    print()
    print("VALIDATION:")
    print("  - Run for 2 minutes")
    print(" - Parse system.json for warmup progression")
    print(" - Expected: Should see logs from 1/10 to 10/10")
    print("  - Reality: If only '1/10' appears → H3.3 VALID")
    print()

    # Clear old logs
    logs_dir = 'logs'
    for f in ['system.json', 'signals.json', 'websocket.json']:
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

    # Validation
    print()
    print("=" * 70)
    print("HYPOTHESIS VALIDATION:")
    print("=" * 70)

    # Check the pattern of warmup logs
    h33_valid = False
    conclusion = ""

    if not warmup_logs:
        print(f"  [UNCERTAIN] H3.3: No warmup logs found")
        print(f"     Cannot determine if warmup logic is working")
        conclusion = "no_logs"
    elif len(warmup_logs) == 1:
        message = warmup_logs[0]['message']
        if "1/10" in message:
            print(f"  [VALID] H3.3 VALID: Only 1 warmup log found with '1/10'")
            print(f"     Expected: Multiple logs showing progression to 10/10")
            print(f"     Found: {message}")
            print(f"     This confirms the logging interval is too large")
            h33_valid = True
            conclusion = "single_log_1_10"
        else:
            print(f"  [INVALID] H3.3 INVALID: Single log but not '1/10'")
            print(f"     Found: {message}")
            conclusion = "single_log_other"
    else:
        # Check if we have progression
        messages = [l['message'] for l in warmup_logs]
        has_progression = any("1/10" in msg for msg in messages) and any("10/10" in msg for msg in messages)
        
        if has_progression:
            print(f"  [INVALID] H3.3 INVALID: Warmup logs show progression")
            print(f"     Found progression logs: {messages}")
            conclusion = "progression_found"
        else:
            print(f"  [VALID] H3.3 VALID: Multiple logs but no proper progression")
            print(f"     Logs: {messages}")
            h33_valid = True
            conclusion = "multiple_logs_no_progression"

    # Additional analysis - check if signals started
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

    print(f"\nSignal logs: {len(signals_logs)}")
    
    # Save results
    results = {
        'test': 'warmup_logging',
        'h33_valid': h33_valid,
        'warmup_log_count': len(warmup_logs),
        'warmup_messages': [l['message'] for l in warmup_logs],
        'signal_log_count': len(signals_logs),
        'conclusion': conclusion
    }

    with open('TESTS/kilo/test_03_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: test_03_results.json")

if __name__ == "__main__":
    asyncio.run(test_warmup_logging())