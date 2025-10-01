"""
Iteration 2 - Test #1: Validate H2.1 & H2.6
Test candles_buffer growth and memory leak

Expected: Rolling window limits buffer to 100 candles
Reality: If buffer grows unbounded → H2.1 VALID
"""
import asyncio
import sys
import os
import time
import psutil
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from main import main
from src.websocket_handler import TradeWebSocket

async def monitor_buffer_and_memory():
    """Monitor candles_buffer size and memory usage"""
    print("=" * 70)
    print("TEST #1: Buffer Growth & Memory Leak Validation")
    print("=" * 70)
    print()
    print("HYPOTHESIS H2.1: candles_buffer grows unbounded (no rolling window)")
    print("HYPOTHESIS H2.6: Memory grows ~18MB/90s -> ~480MB/hour")
    print()
    print("VALIDATION:")
    print("  - Run for 5 minutes (300s)")
    print("  - Monitor candles_buffer size every 30s")
    print("  - Monitor memory (RSS) every 30s")
    print("  - Expected: If rolling window = 100, buffer stays <=100")
    print("  - Expected: If no limit, buffer grows to ~150+ (5min / 10s * coins)")
    print()

    # Get initial memory
    process = psutil.Process()
    initial_memory_mb = process.memory_info().rss / 1024 / 1024

    print(f"Initial memory: {initial_memory_mb:.2f} MB")
    print(f"Starting 5-minute monitoring...")
    print()

    # Create monitoring task
    from src.trading_api import get_all_symbols_by_volume
    from src.config import setup_logging

    setup_logging()
    filtered_coins = get_all_symbols_by_volume()
    aggregator = TradeWebSocket(filtered_coins)

    # Start WebSocket
    ws_task = asyncio.create_task(aggregator.start_connection())

    start_time = time.time()
    measurements = []

    try:
        while time.time() - start_time < 300:  # 5 minutes
            await asyncio.sleep(30)  # Check every 30s

            elapsed = time.time() - start_time
            current_memory_mb = process.memory_info().rss / 1024 / 1024
            memory_growth_mb = current_memory_mb - initial_memory_mb
            memory_growth_pct = (memory_growth_mb / initial_memory_mb) * 100

            # Check buffer sizes
            buffer_sizes = {}
            max_buffer_size = 0
            total_candles = 0

            for coin in filtered_coins[:5]:  # Sample first 5 coins
                if coin in aggregator.candles_buffer:
                    size = len(aggregator.candles_buffer[coin])
                    buffer_sizes[coin] = size
                    max_buffer_size = max(max_buffer_size, size)
                    total_candles += size

            measurement = {
                'time': elapsed,
                'memory_mb': current_memory_mb,
                'growth_mb': memory_growth_mb,
                'growth_pct': memory_growth_pct,
                'max_buffer': max_buffer_size,
                'total_candles_sample': total_candles,
                'buffer_samples': buffer_sizes
            }
            measurements.append(measurement)

            print(f"[{elapsed:.0f}s] Memory: {current_memory_mb:.2f}MB (+{memory_growth_mb:.2f}MB, +{memory_growth_pct:.1f}%) | "
                  f"Max buffer: {max_buffer_size} | Sample total: {total_candles}")

    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    finally:
        await aggregator.stop()

    # Analysis
    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)

    if measurements:
        final = measurements[-1]
        print(f"\nMemory Analysis:")
        print(f"  Initial: {initial_memory_mb:.2f} MB")
        print(f"  Final: {final['memory_mb']:.2f} MB")
        print(f"  Growth: +{final['growth_mb']:.2f} MB (+{final['growth_pct']:.1f}%)")
        print(f"  Projected 1-hour growth: +{final['growth_mb'] * (3600/final['time']):.0f} MB")

        print(f"\nBuffer Analysis:")
        print(f"  Max buffer size: {final['max_buffer']}")
        print(f"  Expected candles per coin: {int(final['time'] / 10)}")
        print(f"  Sample buffer sizes: {final['buffer_samples']}")

        # Validation
        print(f"\nHYPOTHESIS VALIDATION:")

        # H2.1 - Rolling Window
        expected_candles = int(final['time'] / 10)
        if final['max_buffer'] > 100:
            print(f"  ✅ H2.1 VALID: No rolling window detected")
            print(f"     Buffer grew to {final['max_buffer']} (expected ≤100 if rolling)")
            h21_valid = True
        else:
            print(f"  ❌ H2.1 INVALID: Rolling window appears to be working")
            print(f"     Buffer stayed at {final['max_buffer']} (expected {expected_candles})")
            h21_valid = False

        # H2.6 - Memory Growth
        projected_hour_growth = final['growth_mb'] * (3600/final['time'])
        if projected_hour_growth > 200:  # Significant growth
            print(f"  ✅ H2.6 VALID: Memory leak detected")
            print(f"     Projected 1-hour growth: +{projected_hour_growth:.0f}MB")
            h26_valid = True
        else:
            print(f"  ❌ H2.6 INVALID: Memory growth acceptable")
            print(f"     Projected 1-hour growth: +{projected_hour_growth:.0f}MB")
            h26_valid = False

        # Save results
        results = {
            'test': 'buffer_memory',
            'h21_valid': h21_valid,
            'h26_valid': h26_valid,
            'measurements': measurements,
            'conclusions': {
                'max_buffer': final['max_buffer'],
                'expected_buffer': expected_candles,
                'memory_growth_mb': final['growth_mb'],
                'projected_hour_mb': projected_hour_growth
            }
        }

        with open('TESTS/iteration_2/test_01_results.json', 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\nResults saved to: test_01_results.json")

    return measurements

if __name__ == "__main__":
    asyncio.run(monitor_buffer_and_memory())
