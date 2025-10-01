"""
Cross-Audit #3 - Test C4.4 & C4.8: Memory Measurement Validation

Check if multiple processes or measurement errors
"""
import psutil
import os
import time

def check_processes_and_memory():
    """Check for multiple Python processes"""
    print("=" * 70)
    print("CROSS-AUDIT #3: Memory Measurement & Multiple Processes")
    print("=" * 70)
    print()
    print("C4.4 - Check for multiple aggregator instances")
    print("C4.8 - Validate memory measurement stability")
    print()

    # Get current process
    current_pid = os.getpid()
    current_process = psutil.Process(current_pid)

    # Find all Python processes
    python_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'python' in proc.info['name'].lower():
                python_processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cmdline': ' '.join(proc.info['cmdline'] or [])[:100]
                })
        except:
            pass

    print(f"Python processes found: {len(python_processes)}")
    print(f"Current PID: {current_pid}")
    print()

    # Check for multiple instances of our tests
    test_processes = [p for p in python_processes if 'TESTS' in p['cmdline']]
    main_processes = [p for p in python_processes if 'main.py' in p['cmdline']]

    print(f"Test processes: {len(test_processes)}")
    for p in test_processes:
        print(f"  PID {p['pid']}: {p['cmdline']}")

    print(f"\nMain.py processes: {len(main_processes)}")
    for p in main_processes:
        print(f"  PID {p['pid']}: {p['cmdline']}")

    print()

    # C4.4 Validation
    if len(test_processes) > 1 or len(main_processes) > 0:
        print(f"[VALID] C4.4 VALID: Multiple processes detected!")
        print(f"  Test processes: {len(test_processes)}")
        print(f"  Main processes: {len(main_processes)}")
        c44_valid = True
    else:
        print(f"[INVALID] C4.4 INVALID: Only one process")
        c44_valid = False

    print()
    print("-" * 70)
    print()

    # C4.8 - Memory measurement stability
    print(f"C4.8 - Memory Measurement Stability Test")
    print(f"Measuring memory 10 times over 10 seconds...")
    print()

    measurements = []
    for i in range(10):
        # Force GC
        import gc
        gc.collect()

        # Measure
        memory_mb = current_process.memory_info().rss / 1024 / 1024
        measurements.append(memory_mb)

        print(f"  [{i+1}] {memory_mb:.2f} MB")
        time.sleep(1)

    # Calculate variance
    avg = sum(measurements) / len(measurements)
    variance = sum((m - avg) ** 2 for m in measurements) / len(measurements)
    std_dev = variance ** 0.5
    min_mem = min(measurements)
    max_mem = max(measurements)
    range_mem = max_mem - min_mem

    print()
    print(f"Statistics:")
    print(f"  Average: {avg:.2f} MB")
    print(f"  Std Dev: {std_dev:.2f} MB")
    print(f"  Range: {range_mem:.2f} MB (min: {min_mem:.2f}, max: {max_mem:.2f})")

    print()

    # C4.8 Validation
    if range_mem > 5:  # >5 MB variance
        print(f"[VALID] C4.8 VALID: Memory measurement unstable")
        print(f"  Range: {range_mem:.2f} MB (high variance)")
        print(f"  This may explain inconsistent readings in test_01")
        c48_valid = True
    elif std_dev > 2:
        print(f"[PARTIALLY VALID] C4.8: Moderate variance")
        print(f"  Std Dev: {std_dev:.2f} MB")
        c48_valid = True
    else:
        print(f"[INVALID] C4.8 INVALID: Memory measurement stable")
        print(f"  Variance is low: {std_dev:.2f} MB std dev")
        c48_valid = False

    # Save results
    import json
    results = {
        'test': 'memory_measurement_validation',
        'c44_valid': c44_valid,
        'c48_valid': c48_valid,
        'python_processes': len(python_processes),
        'test_processes': len(test_processes),
        'main_processes': len(main_processes),
        'memory_measurements': measurements,
        'memory_stats': {
            'avg': avg,
            'std_dev': std_dev,
            'range': range_mem,
            'min': min_mem,
            'max': max_mem
        }
    }

    with open('TESTS/iteration_2/test_cross_03_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: test_cross_03_results.json")

if __name__ == "__main__":
    check_processes_and_memory()
