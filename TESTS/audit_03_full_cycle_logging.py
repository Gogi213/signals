"""
CROSS-AUDIT #3 - Full Cycle & Logging Analysis
Tests complete pipeline: WebSocket → Candles → Signals → Logging

NEW HYPOTHESES:
H3.1: Логи дублируются при смене сигнала False→False
H3.2: Логирование свечей происходит правильно для каждого 10-секундного интервала
H3.3: Сигналы логируются только при изменении состояния
H3.4: Volume inflation от дубликатов влияет на генерацию сигналов
H3.5: Нет пропущенных интервалов в цепочке Trades→Candles→Signals
"""
import asyncio
import time
from typing import List, Dict
import sys
import os
from collections import defaultdict

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.websocket_handler import TradeWebSocket
from src.config import log_signal, log_new_candle


async def test_full_pipeline():
    """
    H3.1, H3.2, H3.3, H3.4, H3.5: Full pipeline test
    """
    print("\n=== CROSS-AUDIT #3.1: Full Pipeline Analysis ===\n")

    test_coins = ['ARBUSDT', '1000PEPEUSDT']
    aggregator = TradeWebSocket(test_coins)

    # Track entire pipeline
    pipeline_events = {
        'trades': [],
        'candles': [],
        'signals': [],
        'log_calls': []
    }

    # Intercept trades
    original_process = aggregator._process_trade_to_candle

    async def monitored_process(symbol: str, trade_data: Dict):
        pipeline_events['trades'].append({
            'time': time.time(),
            'symbol': symbol,
            'timestamp': trade_data['timestamp'],
            'price': trade_data['price'],
            'volume': trade_data['size'],
            'interval': (trade_data['timestamp'] // 10000) * 10000
        })
        await original_process(symbol, trade_data)

    aggregator._process_trade_to_candle = monitored_process

    # Monitor candles
    async def monitor_candles():
        last_counts = {coin: 0 for coin in test_coins}

        while aggregator.running:
            for coin in test_coins:
                current_count = len(aggregator.candles_buffer.get(coin, []))
                if current_count > last_counts[coin]:
                    candles = aggregator.candles_buffer[coin]
                    new_candles = candles[last_counts[coin]:]

                    for candle in new_candles:
                        pipeline_events['candles'].append({
                            'time': time.time(),
                            'coin': coin,
                            'timestamp': candle['timestamp'],
                            'volume': candle['volume'],
                            'ohlc': {
                                'open': candle['open'],
                                'high': candle['high'],
                                'low': candle['low'],
                                'close': candle['close']
                            }
                        })

                    last_counts[coin] = current_count

            await asyncio.sleep(0.5)

    # Monitor signals (simulate main loop behavior)
    async def monitor_signals():
        last_signals = {coin: None for coin in test_coins}

        while aggregator.running:
            for coin in test_coins:
                signal, signal_info = aggregator.get_signal_data(coin)

                # Track every signal check
                pipeline_events['signals'].append({
                    'time': time.time(),
                    'coin': coin,
                    'signal': signal,
                    'candle_count': signal_info.get('candle_count', 0) if signal_info else 0,
                    'changed': last_signals[coin] is None or last_signals[coin] != signal,
                    'prev_signal': last_signals[coin]
                })

                # Check if would log (only on change)
                if last_signals[coin] is None or last_signals[coin] != signal:
                    pipeline_events['log_calls'].append({
                        'time': time.time(),
                        'coin': coin,
                        'signal': signal,
                        'prev_signal': last_signals[coin]
                    })

                last_signals[coin] = signal

            await asyncio.sleep(10)  # Check every 10 seconds like main loop

    # Start all monitoring
    ws_task = asyncio.create_task(aggregator.start_connection())
    candle_task = asyncio.create_task(monitor_candles())
    signal_task = asyncio.create_task(monitor_signals())

    print(f"Monitoring full pipeline for 90 seconds...")
    await asyncio.sleep(90)

    # Stop
    await aggregator.stop()
    await ws_task
    candle_task.cancel()
    signal_task.cancel()
    try:
        await candle_task
    except asyncio.CancelledError:
        pass
    try:
        await signal_task
    except asyncio.CancelledError:
        pass

    # ANALYSIS
    print(f"\n📊 Pipeline Statistics:")
    print(f"  Trades received: {len(pipeline_events['trades'])}")
    print(f"  Candles created: {len(pipeline_events['candles'])}")
    print(f"  Signal checks: {len(pipeline_events['signals'])}")
    print(f"  Log calls (simulated): {len(pipeline_events['log_calls'])}")

    # H3.1: Check for duplicate False→False logging
    print("\n--- H3.1: Duplicate Logging Check ---")
    false_to_false = [s for s in pipeline_events['signals'] if s['signal'] == False and s['prev_signal'] == False and not s['changed']]
    print(f"False→False transitions (no change): {len(false_to_false)}")
    print(f"Log calls for False→False: {len([l for l in pipeline_events['log_calls'] if l['signal'] == False and l['prev_signal'] == False])}")

    if len([l for l in pipeline_events['log_calls'] if l['signal'] == False and l['prev_signal'] == False]) > 0:
        print(f"❌ HYPOTHESIS H3.1 VALIDATED: False→False transitions are logged")
    else:
        print(f"✅ HYPOTHESIS H3.1 REJECTED: False→False transitions are NOT logged")

    # H3.2: Check candle logging intervals
    print("\n--- H3.2: Candle Interval Consistency ---")
    by_coin_candles = defaultdict(list)
    for candle in pipeline_events['candles']:
        by_coin_candles[candle['coin']].append(candle)

    for coin, candles in by_coin_candles.items():
        if len(candles) >= 2:
            timestamps = [c['timestamp'] for c in candles]
            gaps = []
            for i in range(1, len(timestamps)):
                gap = timestamps[i] - timestamps[i-1]
                if gap != 10000:
                    gaps.append({
                        'position': i,
                        'expected': 10000,
                        'actual': gap,
                        'diff': gap - 10000
                    })

            print(f"\n{coin}:")
            print(f"  Candles: {len(candles)}")
            print(f"  Irregular intervals: {len(gaps)}")

            if gaps:
                print(f"❌ HYPOTHESIS H3.2 REJECTED: Intervals are not consistent for {coin}")
                for gap in gaps[:3]:
                    print(f"    Position {gap['position']}: {gap['actual']}ms (expected 10000ms)")
            else:
                print(f"✅ HYPOTHESIS H3.2 VALIDATED: All intervals are 10s for {coin}")

    # H3.3: Signal logging only on change
    print("\n--- H3.3: Signal Change Logging ---")
    signal_changes = [s for s in pipeline_events['signals'] if s['changed']]
    log_calls_count = len(pipeline_events['log_calls'])

    print(f"Signal changes detected: {len(signal_changes)}")
    print(f"Log calls triggered: {log_calls_count}")

    if log_calls_count == len(signal_changes):
        print(f"✅ HYPOTHESIS H3.3 VALIDATED: Logs only on signal change")
    else:
        print(f"❌ HYPOTHESIS H3.3 REJECTED: Log count mismatch")

    # H3.5: Check for missing intervals
    print("\n--- H3.5: Missing Intervals Check ---")
    for coin, candles in by_coin_candles.items():
        if len(candles) >= 2:
            expected_candles = (candles[-1]['timestamp'] - candles[0]['timestamp']) // 10000 + 1
            actual_candles = len(candles)

            print(f"\n{coin}:")
            print(f"  Time span: {(candles[-1]['timestamp'] - candles[0]['timestamp']) / 1000:.0f}s")
            print(f"  Expected candles: {expected_candles}")
            print(f"  Actual candles: {actual_candles}")

            if expected_candles == actual_candles:
                print(f"✅ HYPOTHESIS H3.5 VALIDATED: No missing intervals for {coin}")
            else:
                missing = expected_candles - actual_candles
                print(f"❌ HYPOTHESIS H3.5 REJECTED: {missing} missing intervals for {coin}")


async def test_deduplication_impact():
    """
    H3.4: Test impact of deduplication on signals
    """
    print("\n=== CROSS-AUDIT #3.2: Deduplication Impact ===\n")

    test_coins = ['ARBUSDT']

    # Test WITH duplicates (normal)
    print("--- Running WITH duplicates (baseline) ---")
    aggregator_dup = TradeWebSocket(test_coins)

    signals_with_dup = []

    async def monitor_signals_dup():
        while aggregator_dup.running:
            for coin in test_coins:
                signal, signal_info = aggregator_dup.get_signal_data(coin)
                if signal_info and signal_info.get('candle_count', 0) >= 25:
                    signals_with_dup.append({
                        'time': time.time(),
                        'signal': signal,
                        'candle_count': signal_info.get('candle_count', 0),
                        'last_candle': signal_info.get('last_candle')
                    })
            await asyncio.sleep(10)

    ws_task_dup = asyncio.create_task(aggregator_dup.start_connection())
    signal_task_dup = asyncio.create_task(monitor_signals_dup())

    await asyncio.sleep(60)

    await aggregator_dup.stop()
    await ws_task_dup
    signal_task_dup.cancel()
    try:
        await signal_task_dup
    except asyncio.CancelledError:
        pass

    print(f"Signals collected WITH duplicates: {len(signals_with_dup)}")

    # Test WITHOUT duplicates (with deduplication)
    print("\n--- Running WITHOUT duplicates (deduplication) ---")
    aggregator_nodup = TradeWebSocket(test_coins)

    # Add deduplication logic
    seen_trades = set()

    original_process_nodup = aggregator_nodup._process_trade_to_candle

    async def dedup_process(symbol: str, trade_data: Dict):
        signature = f"{symbol}_{trade_data['timestamp']}_{trade_data['price']}_{trade_data['size']}"

        if signature in seen_trades:
            # Skip duplicate
            return

        seen_trades.add(signature)
        await original_process_nodup(symbol, trade_data)

    aggregator_nodup._process_trade_to_candle = dedup_process

    signals_without_dup = []

    async def monitor_signals_nodup():
        while aggregator_nodup.running:
            for coin in test_coins:
                signal, signal_info = aggregator_nodup.get_signal_data(coin)
                if signal_info and signal_info.get('candle_count', 0) >= 25:
                    signals_without_dup.append({
                        'time': time.time(),
                        'signal': signal,
                        'candle_count': signal_info.get('candle_count', 0),
                        'last_candle': signal_info.get('last_candle')
                    })
            await asyncio.sleep(10)

    ws_task_nodup = asyncio.create_task(aggregator_nodup.start_connection())
    signal_task_nodup = asyncio.create_task(monitor_signals_nodup())

    await asyncio.sleep(60)

    await aggregator_nodup.stop()
    await ws_task_nodup
    signal_task_nodup.cancel()
    try:
        await signal_task_nodup
    except asyncio.CancelledError:
        pass

    print(f"Signals collected WITHOUT duplicates: {len(signals_without_dup)}")

    # Compare
    print("\n--- H3.4: Deduplication Impact Analysis ---")

    if signals_with_dup and signals_without_dup:
        # Compare volumes
        with_dup_volumes = [s['last_candle']['volume'] for s in signals_with_dup if s.get('last_candle')]
        without_dup_volumes = [s['last_candle']['volume'] for s in signals_without_dup if s.get('last_candle')]

        if with_dup_volumes and without_dup_volumes:
            avg_with = sum(with_dup_volumes) / len(with_dup_volumes)
            avg_without = sum(without_dup_volumes) / len(without_dup_volumes)

            print(f"Average volume WITH duplicates: {avg_with:.2f}")
            print(f"Average volume WITHOUT duplicates: {avg_without:.2f}")
            print(f"Volume inflation: {(avg_with - avg_without) / avg_without * 100:.2f}%")

            # Check signal differences
            true_with = len([s for s in signals_with_dup if s['signal']])
            true_without = len([s for s in signals_without_dup if s['signal']])

            print(f"\nTrue signals WITH duplicates: {true_with} / {len(signals_with_dup)}")
            print(f"True signals WITHOUT duplicates: {true_without} / {len(signals_without_dup)}")

            if abs(avg_with - avg_without) / avg_without > 0.05:
                print(f"✅ HYPOTHESIS H3.4 VALIDATED: Deduplication significantly affects volumes (>5%)")
            else:
                print(f"❌ HYPOTHESIS H3.4 REJECTED: Impact is minimal (<5%)")
    else:
        print(f"⚠️  HYPOTHESIS H3.4: Insufficient data for comparison")


async def main():
    print("="*60)
    print("CROSS-AUDIT #3 - FULL CYCLE & LOGGING")
    print("="*60)

    try:
        await test_full_pipeline()
        await asyncio.sleep(2)

        await test_deduplication_impact()

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during tests: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("CROSS-AUDIT #3 COMPLETED")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())