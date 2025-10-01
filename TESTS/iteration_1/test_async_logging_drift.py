"""
Test async candle logging to verify time drift is eliminated
Runs for 180 seconds monitoring 5+ coins, analyzing drift patterns
"""
import asyncio
import sys
import io
import json
import time
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding for emoji output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.websocket_handler import TradeWebSocket
from src.trading_api import get_all_symbols_by_volume
from src.config import start_candle_logging

async def test_async_logging_drift():
    """Test async candle logging for time drift elimination"""
    print("\n" + "="*80)
    print("ASYNC LOGGING DRIFT TEST - 180 seconds")
    print("="*80)

    # Get filtered coins
    filtered_coins = get_all_symbols_by_volume()
    test_coins = filtered_coins[:5]  # Test with 5 coins

    print(f"\n📊 Testing with {len(test_coins)} coins: {', '.join(test_coins)}")

    # Start async candle logging worker
    start_candle_logging()
    await asyncio.sleep(0.5)  # Give worker time to start

    # Create aggregator
    aggregator = TradeWebSocket(test_coins)

    # Start WebSocket
    ws_task = asyncio.create_task(aggregator.start_connection())

    print("\n⏳ Running test for 180 seconds...")
    print("   Monitoring time drift in candle finalization...")

    start_time = time.time()
    drift_samples = []

    try:
        while time.time() - start_time < 180:
            await asyncio.sleep(5)  # Sample every 5 seconds

            # Read last 20 candle logs from websocket.json
            log_file = Path(project_root) / 'logs' / 'websocket.json'
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    recent_candles = []

                    for line in lines[-100:]:  # Check last 100 lines
                        try:
                            log_entry = json.loads(line)
                            if 'candle_data' in log_entry:
                                recent_candles.append(log_entry)
                        except:
                            pass

                    if recent_candles:
                        # Calculate drift for recent candles
                        drifts = []
                        for entry in recent_candles[-10:]:
                            log_time = datetime.fromisoformat(entry['timestamp'])
                            candle_time = datetime.fromtimestamp(entry['candle_data']['timestamp'] / 1000)
                            drift_ms = (log_time - candle_time).total_seconds() * 1000
                            drifts.append(drift_ms)

                        if drifts:
                            avg_drift = sum(drifts) / len(drifts)
                            drift_samples.append({
                                'elapsed': time.time() - start_time,
                                'drift_ms': avg_drift
                            })

                            elapsed = int(time.time() - start_time)
                            print(f"   [{elapsed:3d}s] Avg drift: {avg_drift:+7.2f}ms (n={len(drifts)})")

    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    finally:
        await aggregator.stop()
        await asyncio.sleep(1)

    # Analyze drift samples
    print("\n" + "="*80)
    print("DRIFT ANALYSIS")
    print("="*80)

    if len(drift_samples) >= 3:
        initial_drift = drift_samples[0]['drift_ms']
        final_drift = drift_samples[-1]['drift_ms']
        drift_change = final_drift - initial_drift

        print(f"\n📈 Initial drift: {initial_drift:+.2f}ms")
        print(f"📈 Final drift:   {final_drift:+.2f}ms")
        print(f"📈 Change:        {drift_change:+.2f}ms over {drift_samples[-1]['elapsed']:.1f}s")

        # Check if drift is stable (change < 500ms)
        if abs(drift_change) < 500:
            print(f"\n✅ DRIFT ELIMINATED: Change of {drift_change:+.2f}ms is acceptable")
        else:
            print(f"\n❌ DRIFT STILL PRESENT: Change of {drift_change:+.2f}ms exceeds threshold")

        # Show drift progression
        print(f"\n📊 Drift progression:")
        for i, sample in enumerate(drift_samples):
            if i % 3 == 0:  # Show every 3rd sample
                print(f"   [{sample['elapsed']:5.1f}s] {sample['drift_ms']:+7.2f}ms")
    else:
        print(f"\n⚠️  Insufficient samples ({len(drift_samples)}) to analyze drift")

    # Check log file integrity
    log_file = Path(project_root) / 'logs' / 'websocket.json'
    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            candle_count = sum(1 for line in lines if 'candle_data' in line)
            print(f"\n✅ Log file created: {candle_count} candle entries written")
    else:
        print(f"\n❌ Log file not found: {log_file}")

if __name__ == "__main__":
    asyncio.run(test_async_logging_drift())
