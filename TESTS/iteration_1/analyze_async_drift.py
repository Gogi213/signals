"""
Analyze websocket.json for time drift after async logging implementation
"""
import json
import sys
import io
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Paths
project_root = Path(__file__).parent.parent
log_file = project_root / 'logs' / 'websocket.json'

print("\n" + "="*80)
print("ASYNC LOGGING DRIFT ANALYSIS")
print("="*80)

if not log_file.exists():
    print(f"\n❌ Log file not found: {log_file}")
    sys.exit(1)

# Parse candle logs
candle_logs = []
with open(log_file, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            log_entry = json.loads(line)
            if 'candle_data' in log_entry:
                candle_logs.append(log_entry)
        except:
            pass

if not candle_logs:
    print(f"\n⚠️  No candle logs found in {log_file}")
    sys.exit(1)

print(f"\n✅ Found {len(candle_logs)} candle log entries")

# Calculate drift for each candle
drifts = []
coins_seen = set()

for log_entry in candle_logs:
    log_time = datetime.fromisoformat(log_entry['timestamp'])
    candle_time = datetime.fromtimestamp(log_entry['candle_data']['timestamp'] / 1000)
    drift_ms = (log_time - candle_time).total_seconds() * 1000

    drifts.append({
        'coin': log_entry.get('coin', 'UNKNOWN'),
        'log_time': log_time,
        'candle_time': candle_time,
        'drift_ms': drift_ms
    })

    coins_seen.add(log_entry.get('coin', 'UNKNOWN'))

print(f"📊 Coins monitored: {len(coins_seen)}")
print(f"   {', '.join(sorted(coins_seen))}")

# Analyze drift progression
first_5 = drifts[:5]
last_5 = drifts[-5:]

print(f"\n📈 First 5 candle drifts:")
for d in first_5:
    print(f"   {d['coin']:12s} {d['drift_ms']:+8.2f}ms  ({d['log_time'].strftime('%H:%M:%S')} vs {d['candle_time'].strftime('%H:%M:%S')})")

print(f"\n📈 Last 5 candle drifts:")
for d in last_5:
    print(f"   {d['coin']:12s} {d['drift_ms']:+8.2f}ms  ({d['log_time'].strftime('%H:%M:%S')} vs {d['candle_time'].strftime('%H:%M:%S')})")

# Calculate stats
first_avg = sum(d['drift_ms'] for d in first_5) / len(first_5)
last_avg = sum(d['drift_ms'] for d in last_5) / len(last_5)
drift_change = last_avg - first_avg

all_drifts = [d['drift_ms'] for d in drifts]
min_drift = min(all_drifts)
max_drift = max(all_drifts)
avg_drift = sum(all_drifts) / len(all_drifts)
drift_range = max_drift - min_drift

print(f"\n" + "="*80)
print("DRIFT STATISTICS")
print("="*80)
print(f"First 5 avg:  {first_avg:+8.2f}ms")
print(f"Last 5 avg:   {last_avg:+8.2f}ms")
print(f"Change:       {drift_change:+8.2f}ms")
print(f"\nMin drift:    {min_drift:+8.2f}ms")
print(f"Max drift:    {max_drift:+8.2f}ms")
print(f"Avg drift:    {avg_drift:+8.2f}ms")
print(f"Range:        {drift_range:8.2f}ms")

# Time span
time_span = (drifts[-1]['log_time'] - drifts[0]['log_time']).total_seconds()
print(f"\nTime span:    {time_span:.1f}s")
print(f"Drift rate:   {drift_change/time_span*60:+.2f}ms/min")

# Verdict
print(f"\n" + "="*80)
if abs(drift_change) < 500:
    print("✅ ASYNC LOGGING SUCCESS: Drift is stable")
    print(f"   Change of {drift_change:+.2f}ms over {time_span:.1f}s is acceptable")
else:
    print("❌ DRIFT STILL PRESENT: Async logging didn't eliminate drift")
    print(f"   Change of {drift_change:+.2f}ms over {time_span:.1f}s exceeds threshold")

if drift_range < 2000:
    print(f"✅ DRIFT RANGE ACCEPTABLE: {drift_range:.2f}ms range is stable")
else:
    print(f"⚠️  DRIFT RANGE HIGH: {drift_range:.2f}ms range indicates instability")

print("="*80)
