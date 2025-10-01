"""
Cross-Audit #2 - Test C3.1, C3.2, C3.3: Memory Leak Sources

Check _trades_by_interval, _seen_trade_signatures, _candle_log_queue sizes
"""
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.trading_api import get_all_symbols_by_volume
from src.config import setup_logging, _candle_log_queue
from src.websocket_handler import TradeWebSocket

async def monitor_memory_sources():
    """Monitor sizes of potential memory leak sources"""
    print("=" * 70)
    print("CROSS-AUDIT #2: Memory Leak Source Detection")
    print("=" * 70)
    print()
    print("Monitoring:")
    print("  C3.1 - _seen_trade_signatures (deduplication)")
    print("  C3.2 - _trades_by_interval (trade accumulation)")
    print("  C3.3 - _candle_log_queue (async logging)")
    print()

    setup_logging()
    filtered_coins = get_all_symbols_by_volume()
    aggregator = TradeWebSocket(filtered_coins)

    # Start WebSocket
    ws_task = asyncio.create_task(aggregator.start_connection())

    print(f"Monitoring {len(filtered_coins)} coins for 2 minutes...")
    print()

    start_time = time.time()
    measurements = []

    try:
        while time.time() - start_time < 120:  # 2 minutes
            await asyncio.sleep(30)  # Check every 30s

            elapsed = time.time() - start_time

            # C3.1 - Deduplication set sizes
            dedup_sizes = {}
            total_dedup = 0
            for coin in filtered_coins[:5]:  # Sample
                if coin in aggregator._seen_trade_signatures:
                    size = len(aggregator._seen_trade_signatures[coin])
                    dedup_sizes[coin] = size
                    total_dedup += size

            # C3.2 - Trades_by_interval sizes
            trades_sizes = {}
            total_trades = 0
            for coin in filtered_coins[:5]:  # Sample
                if coin in aggregator._trades_by_interval:
                    # Count all trades across all intervals
                    count = sum(len(trades) for trades in aggregator._trades_by_interval[coin].values())
                    intervals_count = len(aggregator._trades_by_interval[coin])
                    trades_sizes[coin] = {'trades': count, 'intervals': intervals_count}
                    total_trades += count

            # C3.3 - Logging queue size
            queue_size = _candle_log_queue.qsize()

            measurement = {
                'time': elapsed,
                'dedup_total': total_dedup,
                'dedup_samples': dedup_sizes,
                'trades_total': total_trades,
                'trades_samples': trades_sizes,
                'log_queue_size': queue_size
            }
            measurements.append(measurement)

            print(f"[{elapsed:.0f}s]")
            print(f"  Deduplication sets: {total_dedup} total (sample: {list(dedup_sizes.values())[:3]})")
            print(f"  Trades_by_interval: {total_trades} total (sample: {[(k, v['trades']) for k, v in list(trades_sizes.items())[:3]]})")
            print(f"  Log queue: {queue_size} items")
            print()

    except KeyboardInterrupt:
        print("\nTest interrupted")
    finally:
        await aggregator.stop()

    # Analysis
    print("=" * 70)
    print("HYPOTHESIS VALIDATION")
    print("=" * 70)
    print()

    if measurements:
        first = measurements[0]
        last = measurements[-1]

        # C3.1 - Deduplication
        dedup_growth = last['dedup_total'] - first['dedup_total']
        dedup_growth_rate = dedup_growth / (last['time'] - first['time'])  # per second

        print(f"C3.1 - Deduplication Set Growth:")
        print(f"  Start: {first['dedup_total']}")
        print(f"  End: {last['dedup_total']}")
        print(f"  Growth: +{dedup_growth} ({dedup_growth_rate:.1f}/s)")

        # Estimate memory: ~75 bytes per signature
        dedup_mb = (last['dedup_total'] * 75) / (1024 * 1024)
        print(f"  Estimated memory: {dedup_mb:.2f} MB")

        if dedup_growth_rate > 50:  # Growing fast
            print(f"  [VALID] C3.1 VALID: Deduplication set growing unbounded")
            c31_valid = True
        else:
            print(f"  [INVALID] C3.1 INVALID: Growth rate acceptable")
            c31_valid = False

        print()

        # C3.2 - Trades_by_interval
        trades_growth = last['trades_total'] - first['trades_total']
        trades_growth_rate = trades_growth / (last['time'] - first['time'])

        print(f"C3.2 - Trades_by_interval Accumulation:")
        print(f"  Start: {first['trades_total']}")
        print(f"  End: {last['trades_total']}")
        print(f"  Growth: +{trades_growth} ({trades_growth_rate:.1f}/s)")

        # Estimate memory: ~200 bytes per trade
        trades_mb = (last['trades_total'] * 200) / (1024 * 1024)
        print(f"  Estimated memory: {trades_mb:.2f} MB")
        print(f"  Sample intervals: {last['trades_samples']}")

        if last['trades_total'] > 1000:  # Accumulating
            print(f"  [VALID] C3.2 VALID: Trades accumulating without cleanup")
            c32_valid = True
        else:
            print(f"  [INVALID] C3.2 INVALID: Trades cleaned up properly")
            c32_valid = False

        print()

        # C3.3 - Logging queue
        queue_growth = last['log_queue_size'] - first['log_queue_size']
        queue_growth_rate = queue_growth / (last['time'] - first['time'])

        print(f"C3.3 - Async Logging Queue:")
        print(f"  Start: {first['log_queue_size']}")
        print(f"  End: {last['log_queue_size']}")
        print(f"  Growth: +{queue_growth} ({queue_growth_rate:.1f}/s)")

        # Estimate memory: ~500 bytes per queued candle
        queue_mb = (last['log_queue_size'] * 500) / (1024 * 1024)
        print(f"  Estimated memory: {queue_mb:.2f} MB")

        if last['log_queue_size'] > 100:  # Queue backing up
            print(f"  [VALID] C3.3 VALID: Queue not being processed fast enough")
            c33_valid = True
        else:
            print(f"  [INVALID] C3.3 INVALID: Queue processed properly")
            c33_valid = False

        print()

        # Total estimated memory from tracked sources
        total_tracked_mb = dedup_mb + trades_mb + queue_mb
        print(f"Total tracked memory: {total_tracked_mb:.2f} MB")
        print(f"Actual memory growth (from test_01): ~30 MB")
        print()

        if total_tracked_mb > 20:
            print(f"[CONCLUSION] Major memory leaks identified!")
        elif total_tracked_mb > 5:
            print(f"[CONCLUSION] Moderate memory usage, may contribute to leak")
        else:
            print(f"[CONCLUSION] Tracked sources don't explain leak - check other sources")

        # Save results
        import json
        results = {
            'test': 'memory_leak_sources',
            'c31_valid': c31_valid,
            'c32_valid': c32_valid,
            'c33_valid': c33_valid,
            'measurements': measurements,
            'estimated_memory': {
                'dedup_mb': dedup_mb,
                'trades_mb': trades_mb,
                'queue_mb': queue_mb,
                'total_mb': total_tracked_mb
            }
        }

        with open('TESTS/iteration_2/test_cross_02_results.json', 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\nResults saved to: test_cross_02_results.json")

if __name__ == "__main__":
    asyncio.run(monitor_memory_sources())
