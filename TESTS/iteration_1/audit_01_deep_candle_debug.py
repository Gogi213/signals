"""
AUDIT #1 - Deep Candle Creation Debug
Investigates why candles are not being created in tests
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


async def debug_candle_creation():
    """Deep debug of candle creation process"""
    print("\n=== DEEP DEBUG: Candle Creation Process ===\n")

    test_coins = ['10000LADYSUSDT']
    aggregator = TradeWebSocket(test_coins)

    # Track all internal state changes
    events = []

    # Monitor _trades_by_interval
    async def monitor_state():
        last_trades_count = {}
        last_buffer_count = {}

        while aggregator.running:
            for coin in test_coins:
                # Check _trades_by_interval
                trades_by_interval = aggregator._trades_by_interval.get(coin, {})
                current_intervals = len(trades_by_interval)

                if coin not in last_trades_count:
                    last_trades_count[coin] = 0
                if coin not in last_buffer_count:
                    last_buffer_count[coin] = 0

                if current_intervals != last_trades_count[coin]:
                    events.append({
                        'time': time.time(),
                        'type': 'trades_by_interval_change',
                        'coin': coin,
                        'intervals': list(trades_by_interval.keys()),
                        'count': current_intervals,
                        'details': {k: len(v) for k, v in trades_by_interval.items()}
                    })
                    last_trades_count[coin] = current_intervals

                # Check candles_buffer
                buffer_count = len(aggregator.candles_buffer.get(coin, []))
                if buffer_count != last_buffer_count[coin]:
                    candles = aggregator.candles_buffer[coin]
                    events.append({
                        'time': time.time(),
                        'type': 'candles_buffer_change',
                        'coin': coin,
                        'count': buffer_count,
                        'last_candle': candles[-1] if candles else None
                    })
                    last_buffer_count[coin] = buffer_count

                # Check current_candle_data state
                current_data = aggregator.current_candle_data.get(coin, {})
                if current_data:
                    events.append({
                        'time': time.time(),
                        'type': 'current_candle_state',
                        'coin': coin,
                        'candle_start_time': current_data.get('candle_start_time'),
                        'last_finalized_boundary': current_data.get('last_finalized_boundary'),
                        'trades_count': len(current_data.get('trades', [])),
                        'last_close_price': current_data.get('last_close_price')
                    })

            await asyncio.sleep(2)  # Check every 2 seconds

    # Start monitoring
    ws_task = asyncio.create_task(aggregator.start_connection())
    monitor_task = asyncio.create_task(monitor_state())

    print(f"Monitoring internal state for 40 seconds...")
    await asyncio.sleep(40)

    # Stop
    await aggregator.stop()
    await ws_task
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass

    # ANALYSIS
    print(f"\n📊 Total state change events: {len(events)}")

    # Group by type
    by_type = {}
    for event in events:
        event_type = event['type']
        if event_type not in by_type:
            by_type[event_type] = []
        by_type[event_type].append(event)

    for event_type, event_list in by_type.items():
        print(f"\n--- {event_type} ({len(event_list)} events) ---")
        for i, event in enumerate(event_list[:5]):  # Show first 5
            print(f"  Event {i+1}: {json.dumps(event, indent=2, default=str)}")

    # Final state check
    print(f"\n--- FINAL STATE CHECK ---")
    for coin in test_coins:
        print(f"\nCoin: {coin}")
        print(f"  Candles in buffer: {len(aggregator.candles_buffer.get(coin, []))}")
        print(f"  Trades by interval: {len(aggregator._trades_by_interval.get(coin, {}))}")

        if aggregator.candles_buffer.get(coin):
            print(f"  Last candle: {aggregator.candles_buffer[coin][-1]}")

        trades_by_int = aggregator._trades_by_interval.get(coin, {})
        if trades_by_int:
            print(f"  Trades by interval keys: {list(trades_by_int.keys())[:5]}")

        current_data = aggregator.current_candle_data.get(coin, {})
        print(f"  Current candle start time: {current_data.get('candle_start_time')}")
        print(f"  Last finalized boundary: {current_data.get('last_finalized_boundary')}")
        print(f"  Last close price: {current_data.get('last_close_price')}")


async def test_timer_execution():
    """Check if finalization timer is actually running"""
    print("\n=== TIMER EXECUTION TEST ===\n")

    test_coins = ['10000LADYSUSDT']
    aggregator = TradeWebSocket(test_coins)

    # Track timer executions
    timer_executions = []

    # Patch the finalization timer to track execution
    original_timer = aggregator._candle_finalization_timer

    async def monitored_timer():
        """Monitor timer execution"""
        candle_interval_ms = 10000  # 10 seconds

        # Wait until the next 10-second boundary to start
        current_time_ms = int(time.time() * 1000)
        next_boundary = ((current_time_ms // candle_interval_ms) + 1) * candle_interval_ms
        wait_ms = next_boundary - current_time_ms
        await asyncio.sleep(wait_ms / 1000.0)

        timer_executions.append({
            'time': time.time(),
            'event': 'timer_started'
        })

        while aggregator.running:
            timer_executions.append({
                'time': time.time(),
                'event': 'timer_tick',
                'candles_count': {coin: len(aggregator.candles_buffer.get(coin, [])) for coin in test_coins}
            })

            await asyncio.sleep(10.0)

    aggregator._candle_finalization_timer = monitored_timer

    # Start
    ws_task = asyncio.create_task(aggregator.start_connection())
    print(f"Monitoring timer for 35 seconds...")
    await asyncio.sleep(35)

    await aggregator.stop()
    await ws_task

    # Results
    print(f"\n📊 Timer execution events: {len(timer_executions)}")
    for event in timer_executions:
        print(f"  {json.dumps(event, indent=2, default=str)}")


async def main():
    try:
        await debug_candle_creation()
        await asyncio.sleep(2)

        await test_timer_execution()

    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n\nError during tests: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())