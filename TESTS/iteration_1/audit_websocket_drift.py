"""
AUDIT - WebSocket Time Drift Analysis
Analyzes logs/websocket.json for timestamp drift

HYPOTHESES:
H1: Дрейф в таймстампах свечей (candle timestamp vs real time)
H2: Дрейф в логировании (log timestamp vs candle timestamp)
H3: Свечи отправляются с задержкой относительно их timestamp
"""
import json
import sys
import os
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def analyze_websocket_logs():
    """Analyze websocket.json for time drift"""
    print("\n=== WEBSOCKET TIME DRIFT AUDIT ===\n")

    log_file = os.path.join('logs', 'websocket.json')

    if not os.path.exists(log_file):
        print(f"❌ File not found: {log_file}")
        return

    # Read all log entries
    entries = []
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if 'candle_data' in entry:
                    entries.append(entry)
            except json.JSONDecodeError:
                continue

    print(f"📊 Total candle log entries: {len(entries)}")

    if len(entries) < 10:
        print("⚠️  Not enough data for analysis")
        return

    # Analyze drift
    print("\n--- DRIFT ANALYSIS ---\n")

    drifts = []

    for i, entry in enumerate(entries):
        # Parse timestamps
        log_timestamp = datetime.fromisoformat(entry['timestamp'])
        candle_timestamp_ms = entry['candle_data']['timestamp']
        candle_timestamp = datetime.fromtimestamp(candle_timestamp_ms / 1000)

        # Calculate drift: how much later was the log written compared to candle timestamp
        drift_seconds = (log_timestamp - candle_timestamp).total_seconds()

        drifts.append({
            'index': i,
            'coin': entry.get('coin', 'unknown'),
            'log_time': log_timestamp,
            'candle_time': candle_timestamp,
            'drift_seconds': drift_seconds,
            'candle_timestamp_ms': candle_timestamp_ms,
            'volume': entry['candle_data'].get('volume', 0)
        })

        # Show first 10 and last 10
        if i < 10 or i >= len(entries) - 10:
            log_str = log_timestamp.strftime('%H:%M:%S.%f')[:-3]
            candle_str = candle_timestamp.strftime('%H:%M:%S.%f')[:-3]
            print(f"#{i:3d} {entry['coin']:15s} | Log: {log_str} | Candle: {candle_str} | Drift: {drift_seconds:+6.2f}s")
        elif i == 10:
            print("... (middle entries omitted) ...")

    # Statistics
    print(f"\n--- DRIFT STATISTICS ---\n")

    drift_values = [d['drift_seconds'] for d in drifts]
    min_drift = min(drift_values)
    max_drift = max(drift_values)
    avg_drift = sum(drift_values) / len(drift_values)

    print(f"Min drift: {min_drift:+.2f}s")
    print(f"Max drift: {max_drift:+.2f}s")
    print(f"Avg drift: {avg_drift:+.2f}s")
    print(f"Drift range: {max_drift - min_drift:.2f}s")

    # H1: Check if candle timestamps are exactly on 10s boundaries
    print(f"\n--- H1: Candle Timestamp Alignment ---\n")
    misaligned = []
    for d in drifts:
        ms = d['candle_timestamp_ms']
        boundary = (ms // 10000) * 10000
        if ms != boundary:
            misaligned.append({
                'coin': d['coin'],
                'timestamp': ms,
                'boundary': boundary,
                'diff_ms': ms - boundary
            })

    if misaligned:
        print(f"❌ HYPOTHESIS H1 VALIDATED: {len(misaligned)} candles NOT on 10s boundaries")
        for m in misaligned[:5]:
            print(f"  {m['coin']}: timestamp={m['timestamp']}, expected={m['boundary']}, diff={m['diff_ms']}ms")
    else:
        print(f"✅ HYPOTHESIS H1 REJECTED: All candles on exact 10s boundaries")

    # H2: Check if drift changes over time (logarithmic drift)
    print(f"\n--- H2: Drift Over Time (Logging Drift) ---\n")

    # Compare first 10% vs last 10%
    first_10pct = drifts[:len(drifts)//10]
    last_10pct = drifts[-len(drifts)//10:]

    avg_first = sum(d['drift_seconds'] for d in first_10pct) / len(first_10pct)
    avg_last = sum(d['drift_seconds'] for d in last_10pct) / len(last_10pct)
    drift_change = avg_last - avg_first

    print(f"First 10% avg drift: {avg_first:+.2f}s")
    print(f"Last 10% avg drift:  {avg_last:+.2f}s")
    print(f"Drift change:        {drift_change:+.2f}s")

    if abs(drift_change) > 1.0:
        print(f"❌ HYPOTHESIS H2 VALIDATED: Significant drift change over time (>{drift_change:.2f}s)")
    else:
        print(f"✅ HYPOTHESIS H2 REJECTED: Drift is stable (<1s change)")

    # H3: Check if candles are sent in batches (grouping)
    print(f"\n--- H3: Candle Send Pattern (Batching) ---\n")

    # Group by log second
    by_log_second = {}
    for d in drifts:
        log_second = d['log_time'].replace(microsecond=0)
        if log_second not in by_log_second:
            by_log_second[log_second] = []
        by_log_second[log_second].append(d)

    # Check for batching pattern
    batch_sizes = [len(candles) for candles in by_log_second.values()]
    max_batch = max(batch_sizes)
    avg_batch = sum(batch_sizes) / len(batch_sizes)

    print(f"Max candles per second: {max_batch}")
    print(f"Avg candles per second: {avg_batch:.1f}")
    print(f"Total log seconds: {len(by_log_second)}")

    # Show batching pattern
    print(f"\nBatch size distribution:")
    from collections import Counter
    batch_counter = Counter(batch_sizes)
    for size, count in sorted(batch_counter.items()):
        print(f"  {size} candles/sec: {count} times")

    # Check for periodicity (every 10s bursts)
    print(f"\n--- Periodicity Check (10s bursts) ---\n")

    # Group by 10-second windows
    by_10s_window = {}
    for d in drifts:
        window = (int(d['log_time'].timestamp()) // 10) * 10
        if window not in by_10s_window:
            by_10s_window[window] = []
        by_10s_window[window].append(d)

    window_sizes = [len(candles) for candles in by_10s_window.values()]
    print(f"Candles per 10s window:")
    print(f"  Min: {min(window_sizes)}")
    print(f"  Max: {max(window_sizes)}")
    print(f"  Avg: {sum(window_sizes)/len(window_sizes):.1f}")

    # Check if there's a pattern of delay accumulation
    print(f"\n--- Delay Accumulation Pattern ---\n")

    # Look at drift progression
    if len(drifts) >= 50:
        samples = [drifts[i] for i in range(0, len(drifts), len(drifts)//20)]  # 20 samples
        print("Drift progression (samples):")
        for i, s in enumerate(samples):
            print(f"  Sample {i:2d} (entry #{s['index']:3d}): {s['drift_seconds']:+6.2f}s")

    # Check for monotonic increase (sign of accumulating delay)
    increasing_streak = 0
    max_streak = 0
    for i in range(1, len(drifts)):
        if drifts[i]['drift_seconds'] > drifts[i-1]['drift_seconds']:
            increasing_streak += 1
            max_streak = max(max_streak, increasing_streak)
        else:
            increasing_streak = 0

    print(f"\nLongest increasing drift streak: {max_streak} entries")
    if max_streak > len(drifts) * 0.5:
        print(f"❌ WARNING: Drift is monotonically increasing (delay accumulation)")
    else:
        print(f"✅ Drift is not monotonically increasing")


def main():
    try:
        analyze_websocket_logs()
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()