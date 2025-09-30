"""
AUDIT #1 - WebSocket Trade Reception and Aggregation Tests
Validates hypotheses H1.1, H1.2, H1.7, H1.8
"""
import asyncio
import time
import json
from typing import List, Dict
import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.websocket_handler import TradeWebSocket
from src.config import WARMUP_INTERVALS


async def test_trade_reception_and_timestamps():
    """
    Test H1.1: Check for trade duplication
    Test H1.2: Validate timestamp conversion (microseconds -> milliseconds)
    Test H1.7: Check for zero-volume trades
    """
    print("\n=== AUDIT #1.1: Trade Reception & Timestamps ===\n")

    # Use a single high-volume coin for testing
    test_coins = ['10000LADYSUSDT']

    aggregator = TradeWebSocket(test_coins)

    # Track received trades
    received_trades = []
    original_process = aggregator._process_trade_to_candle

    async def monitored_process(symbol: str, trade_data: Dict):
        """Monitor all trades being processed"""
        received_trades.append({
            'symbol': symbol,
            'timestamp': trade_data['timestamp'],
            'price': trade_data['price'],
            'size': trade_data['size'],
            'time_received': time.time()
        })
        await original_process(symbol, trade_data)

    aggregator._process_trade_to_candle = monitored_process

    # Start connection
    ws_task = asyncio.create_task(aggregator.start_connection())

    # Collect data for 45 seconds (4-5 candles)
    print(f"Collecting trades for 45 seconds...")
    await asyncio.sleep(45)

    # Stop connection
    await aggregator.stop()
    await ws_task

    # HYPOTHESIS VALIDATION
    print(f"\n📊 Total trades received: {len(received_trades)}")

    # H1.1: Check for duplicates
    print("\n--- H1.1: Trade Duplication Check ---")
    trade_signatures = [f"{t['timestamp']}_{t['price']}_{t['size']}" for t in received_trades]
    duplicates = len(trade_signatures) - len(set(trade_signatures))
    print(f"Duplicate trades found: {duplicates}")
    if duplicates > 0:
        print("❌ HYPOTHESIS H1.1 VALIDATED: Duplicates exist")
        # Show examples
        from collections import Counter
        dup_sigs = [sig for sig, count in Counter(trade_signatures).items() if count > 1]
        print(f"Example duplicate signatures (first 3): {dup_sigs[:3]}")
    else:
        print("✅ HYPOTHESIS H1.1 REJECTED: No duplicates")

    # H1.2: Timestamp validation
    print("\n--- H1.2: Timestamp Conversion Check ---")
    current_time_ms = int(time.time() * 1000)
    timestamp_issues = []
    for t in received_trades:
        ts = t['timestamp']
        # Check if timestamp is reasonable (within +/- 1 minute of current time)
        if abs(ts - current_time_ms) > 60000:
            timestamp_issues.append({
                'timestamp': ts,
                'diff_seconds': abs(ts - current_time_ms) / 1000,
                'received_at': t['time_received']
            })

    print(f"Timestamp issues (outside 1-minute window): {len(timestamp_issues)}")
    if timestamp_issues:
        print("❌ HYPOTHESIS H1.2 VALIDATED: Timestamp drift detected")
        print(f"Examples (first 3): {timestamp_issues[:3]}")
    else:
        print("✅ HYPOTHESIS H1.2 REJECTED: Timestamps are accurate")

    # H1.7: Zero volume trades
    print("\n--- H1.7: Zero Volume Trades Check ---")
    zero_volume = [t for t in received_trades if t['size'] == 0]
    print(f"Zero-volume trades found: {len(zero_volume)}")
    if zero_volume:
        print("❌ HYPOTHESIS H1.7 VALIDATED: Zero-volume trades exist")
        print(f"Examples (first 3): {zero_volume[:3]}")
    else:
        print("✅ HYPOTHESIS H1.7 REJECTED: All trades have volume")

    # Additional stats
    print("\n--- Additional Statistics ---")
    if received_trades:
        volumes = [t['size'] for t in received_trades]
        print(f"Volume range: min={min(volumes):.6f}, max={max(volumes):.6f}, avg={sum(volumes)/len(volumes):.6f}")

        prices = [t['price'] for t in received_trades]
        print(f"Price range: min={min(prices):.8f}, max={max(prices):.8f}")


async def test_candle_aggregation_sync():
    """
    Test H1.3: OHLCV aggregation for forward-fill candles
    Test H1.4: Sync between _trades_by_interval and candles_buffer
    Test H1.6: First candle finalization timing
    """
    print("\n=== AUDIT #1.2: Candle Aggregation & Synchronization ===\n")

    test_coins = ['10000LADYSUSDT']
    aggregator = TradeWebSocket(test_coins)

    # Track candle creation
    candle_events = []

    # Monitor candles_buffer changes
    async def monitor_candles():
        last_count = 0
        while aggregator.running:
            for coin in test_coins:
                current_count = len(aggregator.candles_buffer.get(coin, []))
                if current_count > last_count:
                    candles = aggregator.candles_buffer[coin]
                    new_candles = candles[last_count:]
                    for candle in new_candles:
                        candle_events.append({
                            'coin': coin,
                            'timestamp': candle['timestamp'],
                            'volume': candle['volume'],
                            'ohlc': {
                                'open': candle['open'],
                                'high': candle['high'],
                                'low': candle['low'],
                                'close': candle['close']
                            },
                            'time_created': time.time()
                        })
                    last_count = current_count
            await asyncio.sleep(0.5)

    # Start monitoring
    ws_task = asyncio.create_task(aggregator.start_connection())
    monitor_task = asyncio.create_task(monitor_candles())

    # Collect for 35 seconds (3-4 candles)
    print(f"Monitoring candle creation for 35 seconds...")
    await asyncio.sleep(35)

    # Stop
    await aggregator.stop()
    await ws_task
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass

    # VALIDATION
    print(f"\n📊 Total candles created: {len(candle_events)}")

    # H1.3: Forward-fill validation
    print("\n--- H1.3: Forward-Fill OHLCV Check ---")
    zero_volume_candles = [c for c in candle_events if c['volume'] == 0]
    print(f"Zero-volume candles (forward-fill): {len(zero_volume_candles)}")

    if zero_volume_candles:
        print("✅ HYPOTHESIS H1.3 CONFIRMED: Forward-fill candles exist")
        # Check if OHLC are all same
        for i, c in enumerate(zero_volume_candles[:3]):
            ohlc = c['ohlc']
            all_same = (ohlc['open'] == ohlc['high'] == ohlc['low'] == ohlc['close'])
            print(f"  Candle {i+1}: O={ohlc['open']} H={ohlc['high']} L={ohlc['low']} C={ohlc['close']} Same={all_same}")
    else:
        print("⚠️  HYPOTHESIS H1.3: No forward-fill candles detected in test period")

    # H1.4: Check timestamps are sequential
    print("\n--- H1.4: Candle Synchronization Check ---")
    if len(candle_events) >= 2:
        timestamps = [c['timestamp'] for c in candle_events]
        gaps = []
        expected_interval = 10000  # 10 seconds in ms

        for i in range(1, len(timestamps)):
            actual_gap = timestamps[i] - timestamps[i-1]
            if actual_gap != expected_interval:
                gaps.append({
                    'position': i,
                    'expected': expected_interval,
                    'actual': actual_gap,
                    'diff_ms': actual_gap - expected_interval
                })

        print(f"Timestamp gaps (non-10s intervals): {len(gaps)}")
        if gaps:
            print("❌ HYPOTHESIS H1.4 VALIDATED: Synchronization issues detected")
            print(f"Examples (first 3): {gaps[:3]}")
        else:
            print("✅ HYPOTHESIS H1.4 REJECTED: Perfect synchronization")

    # H1.6: First candle timing
    print("\n--- H1.6: First Candle Timing ---")
    if candle_events:
        first_candle = candle_events[0]
        first_timestamp = first_candle['timestamp']
        first_time_created = first_candle['time_created']

        # Check if first candle was created at expected boundary
        expected_boundary = (int(first_time_created * 1000) // 10000) * 10000

        print(f"First candle timestamp: {first_timestamp}")
        print(f"Expected boundary: {expected_boundary}")
        print(f"Difference: {first_timestamp - expected_boundary} ms")

        if first_timestamp < expected_boundary - 10000:
            print("❌ HYPOTHESIS H1.6 VALIDATED: First candle timing issue")
        else:
            print("✅ HYPOTHESIS H1.6 REJECTED: First candle timed correctly")


async def test_lock_contention():
    """
    Test H1.8: Lock contention between trade processing and finalization
    """
    print("\n=== AUDIT #1.3: Lock Contention Analysis ===\n")

    test_coins = ['10000LADYSUSDT']
    aggregator = TradeWebSocket(test_coins)

    # Track lock wait times
    lock_events = []

    # Monkey-patch the lock to track contention
    for coin in test_coins:
        original_lock = aggregator._candle_locks[coin]

        class MonitoredLock:
            def __init__(self, original):
                self._lock = original
                self._acquire_times = []

            async def __aenter__(self):
                start = time.time()
                await self._lock.__aenter__()
                wait_time = time.time() - start
                lock_events.append({
                    'coin': coin,
                    'wait_time_ms': wait_time * 1000,
                    'acquired_at': time.time()
                })
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return await self._lock.__aexit__(exc_type, exc_val, exc_tb)

        aggregator._candle_locks[coin] = MonitoredLock(original_lock)

    # Run for 25 seconds
    ws_task = asyncio.create_task(aggregator.start_connection())
    print(f"Monitoring lock contention for 25 seconds...")
    await asyncio.sleep(25)

    await aggregator.stop()
    await ws_task

    # VALIDATION
    print(f"\n📊 Total lock acquisitions: {len(lock_events)}")

    if lock_events:
        wait_times = [e['wait_time_ms'] for e in lock_events]
        avg_wait = sum(wait_times) / len(wait_times)
        max_wait = max(wait_times)

        print(f"Average lock wait time: {avg_wait:.3f} ms")
        print(f"Maximum lock wait time: {max_wait:.3f} ms")

        # Check for significant contention (>10ms wait)
        contentious = [e for e in lock_events if e['wait_time_ms'] > 10]
        print(f"Contentious locks (>10ms wait): {len(contentious)}")

        if contentious:
            print("❌ HYPOTHESIS H1.8 VALIDATED: Lock contention detected")
            print(f"Examples (first 3): {contentious[:3]}")
        else:
            print("✅ HYPOTHESIS H1.8 REJECTED: No significant lock contention")


async def main():
    """Run all audit tests"""
    print("="*60)
    print("AUDIT #1 - WEBSOCKET TRADE RECEPTION & AGGREGATION")
    print("="*60)

    try:
        await test_trade_reception_and_timestamps()
        await asyncio.sleep(2)

        await test_candle_aggregation_sync()
        await asyncio.sleep(2)

        await test_lock_contention()

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during tests: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("AUDIT #1 COMPLETED")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())