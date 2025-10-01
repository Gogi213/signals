"""
Analyze collected logs for hypothesis generation
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

LOGS_DIR = 'logs'

def analyze_websocket_log():
    """Analyze websocket.json for candle patterns"""
    filepath = os.path.join(LOGS_DIR, 'websocket.json')
    if not os.path.exists(filepath):
        print(f"No websocket.json found")
        return {}

    logs = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                logs.append(json.loads(line))
            except:
                pass

    candle_logs = [l for l in logs if 'candle_data' in l]
    coin_candles = defaultdict(list)

    for log in candle_logs:
        coin = log.get('coin')
        candle_data = log.get('candle_data', {})
        if coin and candle_data:
            coin_candles[coin].append(candle_data)

    print(f"\n=== WEBSOCKET LOG ANALYSIS ===")
    print(f"Total logs: {len(logs)}")
    print(f"Candle logs: {len(candle_logs)}")
    print(f"Unique coins: {len(coin_candles)}")

    # Analyze candle properties
    zero_volume_count = 0
    total_candles = 0
    intervals = []

    for coin, candles in coin_candles.items():
        candles_sorted = sorted(candles, key=lambda x: x['timestamp'])
        total_candles += len(candles_sorted)

        for candle in candles_sorted:
            if candle['volume'] == 0:
                zero_volume_count += 1

        # Check intervals
        for i in range(1, len(candles_sorted)):
            interval = candles_sorted[i]['timestamp'] - candles_sorted[i-1]['timestamp']
            intervals.append(interval)

    print(f"Total candles: {total_candles}")
    print(f"Zero-volume candles: {zero_volume_count} ({zero_volume_count/total_candles*100:.1f}%)")

    if intervals:
        unique_intervals = set(intervals)
        print(f"Interval consistency: {len(unique_intervals)} unique intervals")
        print(f"Expected interval: 10000ms, Found: {unique_intervals}")

    # Show first 3 coins with their candle counts
    print(f"\nSample candle counts:")
    for coin, candles in list(coin_candles.items())[:3]:
        print(f"  {coin}: {len(candles)} candles")

    return {
        'total_candles': total_candles,
        'zero_volume_pct': zero_volume_count/total_candles*100 if total_candles > 0 else 0,
        'unique_coins': len(coin_candles),
        'unique_intervals': len(unique_intervals) if intervals else 0,
        'coin_candles': coin_candles
    }

def analyze_signals_log():
    """Analyze signals.json for signal patterns"""
    filepath = os.path.join(LOGS_DIR, 'signals.json')
    if not os.path.exists(filepath):
        print(f"No signals.json found")
        return {}

    logs = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                logs.append(json.loads(line))
            except:
                pass

    print(f"\n=== SIGNALS LOG ANALYSIS ===")
    print(f"Total signal logs: {len(logs)}")

    true_signals = [l for l in logs if l.get('signal_type') == 'true']
    false_signals = [l for l in logs if l.get('signal_type') == 'false']

    print(f"TRUE signals: {len(true_signals)}")
    print(f"FALSE signals: {len(false_signals)}")

    # Analyze criteria failures
    criteria_failures = defaultdict(int)

    for log in false_signals:
        criteria = log.get('criteria_details', {})
        if isinstance(criteria, dict):
            for crit_name, details in criteria.items():
                if isinstance(details, dict) and not details.get('passed', True):
                    criteria_failures[crit_name] += 1

    print(f"\nCriteria failure counts:")
    for crit, count in sorted(criteria_failures.items(), key=lambda x: -x[1]):
        print(f"  {crit}: {count}")

    return {
        'total_signals': len(logs),
        'true_count': len(true_signals),
        'false_count': len(false_signals),
        'criteria_failures': dict(criteria_failures)
    }

def analyze_system_log():
    """Analyze system.json for warmup and connection events"""
    filepath = os.path.join(LOGS_DIR, 'system.json')
    if not os.path.exists(filepath):
        print(f"No system.json found")
        return {}

    logs = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                logs.append(json.loads(line))
            except:
                pass

    print(f"\n=== SYSTEM LOG ANALYSIS ===")
    print(f"Total system logs: {len(logs)}")

    warmup_logs = [l for l in logs if 'Warmup' in l.get('message', '')]
    connection_logs = [l for l in logs if 'Connected' in l.get('message', '')]

    print(f"Warmup logs: {len(warmup_logs)}")
    print(f"Connection logs: {len(connection_logs)}")

    if warmup_logs:
        print(f"\nWarmup progression:")
        for log in warmup_logs:
            print(f"  {log['message']}")

    return {
        'total_logs': len(logs),
        'warmup_count': len(warmup_logs),
        'connection_count': len(connection_logs)
    }

if __name__ == "__main__":
    ws_data = analyze_websocket_log()
    sig_data = analyze_signals_log()
    sys_data = analyze_system_log()

    print(f"\n=== SUMMARY ===")
    print(f"Candles collected: {ws_data.get('total_candles', 0)}")
    print(f"Signals checked: {sig_data.get('total_signals', 0)}")
    print(f"System events: {sys_data.get('total_logs', 0)}")
