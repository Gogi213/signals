"""
Final 3-minute test to verify:
1. Warmup completes in ~2 minutes (10 candles)
2. signals.json is created
3. Failed signals are logged every iteration
"""
import asyncio
import sys
import io
import json
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Clear old signals.json
signals_log = project_root / 'logs' / 'signals.json'
if signals_log.exists():
    signals_log.unlink()
    print(f"🗑️  Cleared old signals.json")

from src.websocket_handler import TradeWebSocket
from src.trading_api import get_all_symbols_by_volume
from src.config import start_candle_logging, log_signal, WARMUP_INTERVALS
import time as time_module

async def final_test():
    """Final 3-minute integration test"""
    print("\n" + "="*80)
    print(f"FINAL 3-MINUTE TEST (WARMUP={WARMUP_INTERVALS} candles = {WARMUP_INTERVALS*10}s)")
    print("="*80)

    filtered_coins = get_all_symbols_by_volume()
    test_coins = filtered_coins[:5]

    print(f"\n📊 Testing with {len(test_coins)} coins: {', '.join(test_coins)}")

    start_candle_logging()
    await asyncio.sleep(0.5)

    aggregator = TradeWebSocket(test_coins)
    ws_task = asyncio.create_task(aggregator.start_connection())

    print("\n⏳ Running 3-minute test...")

    start_time = time.time()
    warmup_complete = False
    signal_log_count = 0
    last_check_time = start_time

    try:
        while time.time() - start_time < 180:  # 3 minutes
            await asyncio.sleep(0.3)

            # Check warmup status
            warmup_active = False
            min_candles = float('inf')
            coin_signals = {}

            for coin in test_coins:
                signal, signal_info = aggregator.get_signal_data(coin)
                coin_signals[coin] = (signal, signal_info)

                if signal_info and 'criteria' in signal_info:
                    criteria = signal_info['criteria']
                    if criteria.get('validation_error', '').startswith('Warmup:'):
                        warmup_active = True
                        candle_count = signal_info.get('candle_count', 0)
                        min_candles = min(min_candles, candle_count)

            # Update warmup flag
            if not warmup_active and not warmup_complete:
                warmup_complete = True
                elapsed = int(time.time() - start_time)
                print(f"\n✅ WARMUP COMPLETE at {elapsed}s")

            # Log signals after warmup
            if warmup_complete:
                for coin, (signal, signal_info) in coin_signals.items():
                    log_signal(coin, signal, signal_info, warmup_complete=True)

            # Report every 15 seconds
            if time.time() - last_check_time >= 15:
                elapsed = int(time.time() - start_time)

                if warmup_active and min_candles != float('inf'):
                    print(f"   [{elapsed:3d}s] Warmup: {min_candles}/{WARMUP_INTERVALS} candles")
                elif warmup_complete:
                    # Check signals.json
                    if signals_log.exists():
                        with open(signals_log, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            new_count = len(lines)
                            added = new_count - signal_log_count
                            signal_log_count = new_count
                            print(f"   [{elapsed:3d}s] signals.json: {new_count} entries (+{added} since last check)")

                last_check_time = time.time()

    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
    finally:
        await aggregator.stop()
        await asyncio.sleep(1)

    # Final report
    print("\n" + "="*80)
    print("FINAL REPORT")
    print("="*80)

    elapsed = int(time.time() - start_time)
    print(f"\n⏱️  Test duration: {elapsed}s")

    if signals_log.exists():
        with open(signals_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            total_entries = len(lines)

        print(f"\n✅ signals.json CREATED")
        print(f"   Total entries: {total_entries}")

        # Count by type
        true_count = sum(1 for line in lines if '"signal_type": "true"' in line)
        false_count = sum(1 for line in lines if '"signal_type": "false"' in line)

        print(f"   TRUE signals:  {true_count}")
        print(f"   FALSE signals: {false_count}")

        # Show sample entries
        if total_entries > 0:
            print(f"\n📊 First 3 signal entries:")
            for i, line in enumerate(lines[:3]):
                data = json.loads(line)
                coin = data.get('coin', 'UNKNOWN')
                signal_type = data.get('signal_type', 'unknown')

                criteria = data.get('criteria_details', {})
                if 'criteria_details' in criteria:
                    details = criteria['criteria_details']
                    passed = [k for k, v in details.items() if v.get('passed')]
                    failed = [k for k, v in details.items() if not v.get('passed')]
                    print(f"   [{i+1}] {coin:15s} | signal={signal_type:5s} | passed={len(passed)} failed={len(failed)}")
                else:
                    print(f"   [{i+1}] {coin:15s} | signal={signal_type:5s}")

        print(f"\n📈 Signals per second: {total_entries / elapsed:.2f}")
        print(f"📈 Expected rate: ~{len(test_coins) * 3.33:.1f}/s (5 coins × 3.33 Hz)")

    else:
        print(f"\n❌ signals.json NOT CREATED")
        print(f"   Warmup complete: {warmup_complete}")

    print("\n" + "="*80)

if __name__ == "__main__":
    asyncio.run(final_test())
