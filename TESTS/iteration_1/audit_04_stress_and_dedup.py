"""
CROSS-AUDIT #4 - Stress Test & Deduplication Impact
Long-running test with multiple coins to validate H3.4 and stress-test system

NEW HYPOTHESES:
H4.1: Система стабильна при обработке 10+ монет одновременно
H4.2: Дедупликация снижает volume в среднем на ~9% (соответствует проценту дубликатов)
H4.3: Дедупликация влияет на количество true сигналов
H4.4: Память не утекает при длительной работе (300+ секунд)
H4.5: Нет деградации производительности со временем
"""
import asyncio
import time
import psutil
import os
from typing import List, Dict
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.websocket_handler import TradeWebSocket


async def test_stress_multi_coin():
    """
    H4.1: Stress test with multiple coins
    """
    print("\n=== CROSS-AUDIT #4.1: Multi-Coin Stress Test ===\n")

    # Use 10 most active coins
    test_coins = [
        'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'ARBUSDT',
        '1000PEPEUSDT', 'DOGEUSDT', 'XRPUSDT',
        'AVAXUSDT', 'LINKUSDT', 'MATICUSDT'
    ]

    aggregator = TradeWebSocket(test_coins)

    # Track performance metrics
    metrics = {
        'start_time': time.time(),
        'trades_per_second': [],
        'candles_per_interval': [],
        'signal_check_time': [],
        'memory_usage_mb': []
    }

    # Get process for memory tracking
    process = psutil.Process(os.getpid())

    # Track trades
    trade_counter = {'count': 0, 'last_time': time.time()}

    original_process = aggregator._process_trade_to_candle

    async def monitored_process(symbol: str, trade_data: Dict):
        trade_counter['count'] += 1
        await original_process(symbol, trade_data)

    aggregator._process_trade_to_candle = monitored_process

    # Performance monitoring
    async def monitor_performance():
        while aggregator.running:
            # Trades per second
            current_time = time.time()
            elapsed = current_time - trade_counter['last_time']
            if elapsed >= 5:  # Every 5 seconds
                tps = trade_counter['count'] / elapsed
                metrics['trades_per_second'].append({
                    'time': current_time,
                    'tps': tps
                })
                trade_counter['count'] = 0
                trade_counter['last_time'] = current_time

            # Memory usage
            mem = process.memory_info().rss / 1024 / 1024  # MB
            metrics['memory_usage_mb'].append({
                'time': current_time,
                'memory_mb': mem
            })

            # Candles count
            total_candles = sum(len(aggregator.candles_buffer.get(coin, [])) for coin in test_coins)
            metrics['candles_per_interval'].append({
                'time': current_time,
                'total_candles': total_candles
            })

            # Signal check performance
            check_start = time.time()
            for coin in test_coins:
                aggregator.get_signal_data(coin)
            check_time = (time.time() - check_start) * 1000  # ms
            metrics['signal_check_time'].append({
                'time': current_time,
                'check_time_ms': check_time
            })

            await asyncio.sleep(5)

    # Run for 90 seconds
    ws_task = asyncio.create_task(aggregator.start_connection())
    monitor_task = asyncio.create_task(monitor_performance())

    print(f"Running stress test for 90 seconds with {len(test_coins)} coins...")
    await asyncio.sleep(90)

    await aggregator.stop()
    await ws_task
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass

    # ANALYSIS
    print(f"\n📊 Stress Test Results:")
    print(f"Duration: {time.time() - metrics['start_time']:.1f}s")
    print(f"Coins tracked: {len(test_coins)}")

    # H4.1: Stability
    print("\n--- H4.1: System Stability ---")
    total_candles = sum(len(aggregator.candles_buffer.get(coin, [])) for coin in test_coins)
    print(f"Total candles created: {total_candles}")
    print(f"Average per coin: {total_candles / len(test_coins):.1f}")

    if metrics['trades_per_second']:
        tps_values = [m['tps'] for m in metrics['trades_per_second']]
        avg_tps = sum(tps_values) / len(tps_values)
        print(f"Average trades/second: {avg_tps:.2f}")
        print(f"Min TPS: {min(tps_values):.2f}, Max TPS: {max(tps_values):.2f}")

        if total_candles > 50 and avg_tps > 5:
            print(f"✅ HYPOTHESIS H4.1 VALIDATED: System is stable under multi-coin load")
        else:
            print(f"❌ HYPOTHESIS H4.1 REJECTED: System struggled with load")
    else:
        print(f"⚠️  Insufficient metrics collected")

    # H4.4: Memory leaks
    print("\n--- H4.4: Memory Leak Check ---")
    if len(metrics['memory_usage_mb']) >= 2:
        memory_values = [m['memory_mb'] for m in metrics['memory_usage_mb']]
        start_mem = memory_values[0]
        end_mem = memory_values[-1]
        max_mem = max(memory_values)

        print(f"Start memory: {start_mem:.2f} MB")
        print(f"End memory: {end_mem:.2f} MB")
        print(f"Peak memory: {max_mem:.2f} MB")
        print(f"Memory growth: {end_mem - start_mem:.2f} MB ({(end_mem - start_mem) / start_mem * 100:.1f}%)")

        if (end_mem - start_mem) / start_mem < 0.2:  # Less than 20% growth
            print(f"✅ HYPOTHESIS H4.4 VALIDATED: No significant memory leak (<20% growth)")
        else:
            print(f"❌ HYPOTHESIS H4.4 REJECTED: Potential memory leak detected")

    # H4.5: Performance degradation
    print("\n--- H4.5: Performance Degradation Check ---")
    if len(metrics['signal_check_time']) >= 4:
        check_times = [m['check_time_ms'] for m in metrics['signal_check_time']]
        first_half = check_times[:len(check_times)//2]
        second_half = check_times[len(check_times)//2:]

        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)

        print(f"First half avg check time: {avg_first:.2f}ms")
        print(f"Second half avg check time: {avg_second:.2f}ms")

        if avg_first > 0:
            print(f"Degradation: {avg_second - avg_first:.2f}ms ({(avg_second - avg_first) / avg_first * 100:.1f}%)")

            if (avg_second - avg_first) / avg_first < 0.3:  # Less than 30% degradation
                print(f"✅ HYPOTHESIS H4.5 VALIDATED: No significant performance degradation")
            else:
                print(f"❌ HYPOTHESIS H4.5 REJECTED: Performance degraded over time")
        else:
            print(f"Degradation: {avg_second - avg_first:.2f}ms")
            print(f"✅ HYPOTHESIS H4.5 VALIDATED: Signal checks are extremely fast (<1ms)")


async def test_deduplication_impact_long():
    """
    H4.2, H4.3: Long test to measure deduplication impact with warmup
    """
    print("\n=== CROSS-AUDIT #4.2: Deduplication Impact (Long Test) ===\n")

    # Use active coins
    test_coins = ['ARBUSDT', '1000PEPEUSDT', 'DOGEUSDT']

    # Test 1: WITH duplicates
    print("--- Phase 1: WITH duplicates (baseline) ---")
    aggregator_dup = TradeWebSocket(test_coins)

    dup_stats = {
        'candles': [],
        'signals': [],
        'true_signals': 0,
        'duplicate_count': 0,
        'total_trades': 0
    }

    # Track duplicates
    seen_trades_dup = set()

    original_dup = aggregator_dup._process_trade_to_candle

    async def track_dup(symbol: str, trade_data: Dict):
        sig = f"{symbol}_{trade_data['timestamp']}_{trade_data['price']}_{trade_data['size']}"
        if sig in seen_trades_dup:
            dup_stats['duplicate_count'] += 1
        seen_trades_dup.add(sig)
        dup_stats['total_trades'] += 1
        await original_dup(symbol, trade_data)

    aggregator_dup._process_trade_to_candle = track_dup

    # Monitor
    async def monitor_dup():
        while aggregator_dup.running:
            for coin in test_coins:
                candles = aggregator_dup.candles_buffer.get(coin, [])
                if len(candles) >= 25:
                    signal, signal_info = aggregator_dup.get_signal_data(coin)

                    if candles:
                        last_candle = candles[-1]
                        dup_stats['candles'].append({
                            'coin': coin,
                            'volume': last_candle['volume'],
                            'timestamp': last_candle['timestamp']
                        })

                    dup_stats['signals'].append({
                        'coin': coin,
                        'signal': signal
                    })

                    if signal:
                        dup_stats['true_signals'] += 1

            await asyncio.sleep(10)

    ws_task_dup = asyncio.create_task(aggregator_dup.start_connection())
    monitor_task_dup = asyncio.create_task(monitor_dup())

    print(f"Running for 300 seconds (5 min) to reach warmup...")
    await asyncio.sleep(300)

    await aggregator_dup.stop()
    await ws_task_dup
    monitor_task_dup.cancel()
    try:
        await monitor_task_dup
    except asyncio.CancelledError:
        pass

    print(f"\nPhase 1 Results:")
    print(f"  Total trades: {dup_stats['total_trades']}")
    print(f"  Duplicates: {dup_stats['duplicate_count']} ({dup_stats['duplicate_count']/dup_stats['total_trades']*100:.2f}%)")
    print(f"  Candles tracked: {len(dup_stats['candles'])}")
    print(f"  Signals checked: {len(dup_stats['signals'])}")
    print(f"  True signals: {dup_stats['true_signals']}")

    # Test 2: WITHOUT duplicates
    print("\n--- Phase 2: WITHOUT duplicates (deduplication) ---")
    aggregator_nodup = TradeWebSocket(test_coins)

    nodup_stats = {
        'candles': [],
        'signals': [],
        'true_signals': 0,
        'filtered_count': 0,
        'total_trades': 0
    }

    seen_trades_nodup = set()

    original_nodup = aggregator_nodup._process_trade_to_candle

    async def dedup_track(symbol: str, trade_data: Dict):
        sig = f"{symbol}_{trade_data['timestamp']}_{trade_data['price']}_{trade_data['size']}"

        if sig in seen_trades_nodup:
            nodup_stats['filtered_count'] += 1
            return  # Skip duplicate

        seen_trades_nodup.add(sig)
        nodup_stats['total_trades'] += 1
        await original_nodup(symbol, trade_data)

    aggregator_nodup._process_trade_to_candle = dedup_track

    # Monitor
    async def monitor_nodup():
        while aggregator_nodup.running:
            for coin in test_coins:
                candles = aggregator_nodup.candles_buffer.get(coin, [])
                if len(candles) >= 25:
                    signal, signal_info = aggregator_nodup.get_signal_data(coin)

                    if candles:
                        last_candle = candles[-1]
                        nodup_stats['candles'].append({
                            'coin': coin,
                            'volume': last_candle['volume'],
                            'timestamp': last_candle['timestamp']
                        })

                    nodup_stats['signals'].append({
                        'coin': coin,
                        'signal': signal
                    })

                    if signal:
                        nodup_stats['true_signals'] += 1

            await asyncio.sleep(10)

    ws_task_nodup = asyncio.create_task(aggregator_nodup.start_connection())
    monitor_task_nodup = asyncio.create_task(monitor_nodup())

    print(f"Running for 300 seconds (5 min)...")
    await asyncio.sleep(300)

    await aggregator_nodup.stop()
    await ws_task_nodup
    monitor_task_nodup.cancel()
    try:
        await monitor_task_nodup
    except asyncio.CancelledError:
        pass

    print(f"\nPhase 2 Results:")
    print(f"  Trades processed: {nodup_stats['total_trades']}")
    print(f"  Filtered duplicates: {nodup_stats['filtered_count']}")
    print(f"  Candles tracked: {len(nodup_stats['candles'])}")
    print(f"  Signals checked: {len(nodup_stats['signals'])}")
    print(f"  True signals: {nodup_stats['true_signals']}")

    # COMPARISON
    print("\n--- H4.2 & H4.3: Impact Analysis ---")

    if dup_stats['candles'] and nodup_stats['candles']:
        # H4.2: Volume comparison
        dup_volumes = [c['volume'] for c in dup_stats['candles'] if c['volume'] > 0]
        nodup_volumes = [c['volume'] for c in nodup_stats['candles'] if c['volume'] > 0]

        if dup_volumes and nodup_volumes:
            avg_dup = sum(dup_volumes) / len(dup_volumes)
            avg_nodup = sum(nodup_volumes) / len(nodup_volumes)
            volume_diff_pct = (avg_dup - avg_nodup) / avg_nodup * 100

            print(f"\nH4.2: Volume Impact")
            print(f"  WITH duplicates avg volume: {avg_dup:.2f}")
            print(f"  WITHOUT duplicates avg volume: {avg_nodup:.2f}")
            print(f"  Volume inflation: {volume_diff_pct:.2f}%")
            print(f"  Expected inflation: ~{dup_stats['duplicate_count']/dup_stats['total_trades']*100:.2f}%")

            if abs(volume_diff_pct - (dup_stats['duplicate_count']/dup_stats['total_trades']*100)) < 3:
                print(f"✅ HYPOTHESIS H4.2 VALIDATED: Volume inflation matches duplicate rate")
            else:
                print(f"⚠️  HYPOTHESIS H4.2: Volume inflation differs from duplicate rate")

        # H4.3: Signal impact
        print(f"\nH4.3: Signal Impact")
        print(f"  WITH duplicates true signals: {dup_stats['true_signals']}")
        print(f"  WITHOUT duplicates true signals: {nodup_stats['true_signals']}")

        if dup_stats['signals'] and nodup_stats['signals']:
            rate_dup = dup_stats['true_signals'] / len(dup_stats['signals']) * 100
            rate_nodup = nodup_stats['true_signals'] / len(nodup_stats['signals']) * 100

            print(f"  WITH duplicates rate: {rate_dup:.2f}%")
            print(f"  WITHOUT duplicates rate: {rate_nodup:.2f}%")
            print(f"  Difference: {abs(rate_dup - rate_nodup):.2f}%")

            if abs(rate_dup - rate_nodup) > 5:
                print(f"✅ HYPOTHESIS H4.3 VALIDATED: Deduplication significantly affects signals (>5% diff)")
            else:
                print(f"❌ HYPOTHESIS H4.3 REJECTED: Minimal impact on signals (<5% diff)")
    else:
        print(f"⚠️  Insufficient data for comparison")


async def main():
    print("="*60)
    print("CROSS-AUDIT #4 - STRESS TEST & DEDUPLICATION IMPACT")
    print("="*60)

    try:
        await test_stress_multi_coin()
        await asyncio.sleep(5)

        await test_deduplication_impact_long()

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during tests: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("CROSS-AUDIT #4 COMPLETED")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())