"""
Wait for warmup to complete and check if signals.json is created
"""
import asyncio
import sys
import io
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

async def monitor_warmup():
    """Monitor warmup completion"""
    print("\n" + "="*80)
    print("WARMUP MONITORING")
    print("="*80)

    system_log = project_root / 'logs' / 'system.json'
    signals_log = project_root / 'logs' / 'signals.json'

    print(f"\n📊 Monitoring: {system_log}")
    print(f"📊 Watching for: {signals_log}")

    start_time = time.time()
    last_candle_count = 0
    warmup_complete = False

    while time.time() - start_time < 900:  # 15 minutes max
        await asyncio.sleep(10)

        # Check system log for warmup progress
        if system_log.exists():
            with open(system_log, 'r') as f:
                lines = f.readlines()
                for line in reversed(lines[-20:]):  # Check last 20 lines
                    if 'Warmup progress:' in line:
                        import json
                        data = json.loads(line)
                        msg = data['message']
                        # Extract "X/Y" from "Warmup progress: X/Y"
                        parts = msg.split(':')[1].strip().split('/')
                        current = int(parts[0])
                        required = int(parts[1])

                        if current != last_candle_count:
                            elapsed = int(time.time() - start_time)
                            print(f"   [{elapsed:3d}s] Warmup: {current}/{required} candles")
                            last_candle_count = current

                        if current >= required:
                            warmup_complete = True
                            print(f"\n✅ WARMUP COMPLETE at {current} candles")
                            break
                        break

        # Check if signals.json created
        if signals_log.exists():
            size = signals_log.stat().st_size
            print(f"\n✅ signals.json CREATED (size: {size} bytes)")

            # Show first few entries
            with open(signals_log, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                print(f"\n📊 First {min(3, len(lines))} signal entries:")
                for i, line in enumerate(lines[:3]):
                    import json
                    data = json.loads(line)
                    coin = data.get('coin', 'UNKNOWN')
                    signal_type = data.get('signal_type', 'unknown')
                    print(f"   [{i+1}] {coin:15s} signal={signal_type}")
            break

        if warmup_complete and not signals_log.exists():
            print(f"\n⚠️  Warmup complete but signals.json not created yet...")
            await asyncio.sleep(5)

    if not signals_log.exists():
        print(f"\n❌ signals.json NOT CREATED after {int(time.time() - start_time)}s")

    print("\n" + "="*80)

if __name__ == "__main__":
    asyncio.run(monitor_warmup())
