"""
CROSS-AUDIT #2 - Trade Duplication Deep Dive
Investigates H1.1 (validated) and related hypotheses

NEW HYPOTHESES:
H2.1: Дубликаты возникают из-за одновременной отправки одного и того же трейда в WebSocket
H2.2: Дубликаты коррелируют с определенными временными интервалами (пограничные условия)
H2.3: Дубликаты чаще возникают при высокой частоте трейдов
H2.4: Bybit API сам отправляет дубликаты
H2.5: Дубликаты влияют на корректность OHLCV (завышают объем)
"""
import asyncio
import time
from typing import List, Dict, Tuple
import sys
import os
from collections import Counter, defaultdict

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.websocket_handler import TradeWebSocket


async def test_duplication_patterns():
    """
    H2.1, H2.2, H2.3: Analyze duplication patterns
    """
    print("\n=== CROSS-AUDIT #2.1: Duplication Pattern Analysis ===\n")

    # Use multiple coins to increase trade frequency
    test_coins = ['10000LADYSUSDT', 'ARBUSDT', '1000PEPEUSDT']
    aggregator = TradeWebSocket(test_coins)

    # Track ALL incoming trades with microsecond precision
    all_trades = []
    duplicate_events = []

    # Intercept trade processing
    original_process = aggregator._process_trade_to_candle

    async def monitored_process(symbol: str, trade_data: Dict):
        trade_signature = f"{symbol}_{trade_data['timestamp']}_{trade_data['price']}_{trade_data['size']}"

        # Check if already seen
        existing = [t for t in all_trades if t['signature'] == trade_signature]
        if existing:
            duplicate_events.append({
                'signature': trade_signature,
                'symbol': symbol,
                'timestamp': trade_data['timestamp'],
                'first_seen': existing[0]['received_at'],
                'duplicate_seen': time.time(),
                'time_diff_ms': (time.time() - existing[0]['received_at']) * 1000
            })

        all_trades.append({
            'signature': trade_signature,
            'symbol': symbol,
            'timestamp': trade_data['timestamp'],
            'price': trade_data['price'],
            'size': trade_data['size'],
            'received_at': time.time(),
            'candle_boundary': (trade_data['timestamp'] // 10000) * 10000
        })

        await original_process(symbol, trade_data)

    aggregator._process_trade_to_candle = monitored_process

    # Start monitoring
    ws_task = asyncio.create_task(aggregator.start_connection())
    print(f"Monitoring for 120 seconds (2 minutes)...")
    await asyncio.sleep(120)

    await aggregator.stop()
    await ws_task

    # ANALYSIS
    print(f"\n📊 Total trades received: {len(all_trades)}")
    print(f"📊 Duplicate events detected: {len(duplicate_events)}")

    # H2.1: Are duplicates from WebSocket or internal?
    print("\n--- H2.1: Duplication Source ---")
    if duplicate_events:
        print(f"✅ HYPOTHESIS H2.1 VALIDATED: Duplicates detected in WebSocket stream")
        print(f"Duplication rate: {len(duplicate_events) / len(all_trades) * 100:.2f}%")

        # Show time differences between duplicate arrivals
        time_diffs = [d['time_diff_ms'] for d in duplicate_events]
        if time_diffs:
            avg_diff = sum(time_diffs) / len(time_diffs)
            min_diff = min(time_diffs)
            max_diff = max(time_diffs)
            print(f"Time between duplicates: avg={avg_diff:.2f}ms, min={min_diff:.2f}ms, max={max_diff:.2f}ms")

        # Show examples
        print(f"\nDuplicate examples (first 5):")
        for i, dup in enumerate(duplicate_events[:5]):
            print(f"  {i+1}. {dup['symbol']} | timestamp={dup['timestamp']} | diff={dup['time_diff_ms']:.2f}ms")
    else:
        print(f"❌ HYPOTHESIS H2.1 REJECTED: No duplicates in this test")

    # H2.2: Check if duplicates correlate with boundaries
    print("\n--- H2.2: Boundary Correlation ---")
    if duplicate_events:
        boundary_issues = []
        for dup in duplicate_events:
            # Find original trade
            original = [t for t in all_trades if t['signature'] == dup['signature']][0]
            timestamp = original['timestamp']
            boundary = original['candle_boundary']

            # Check if near boundary (within 500ms)
            distance_to_boundary = min(
                timestamp - boundary,
                boundary + 10000 - timestamp
            )

            boundary_issues.append({
                'distance_ms': distance_to_boundary,
                'near_boundary': distance_to_boundary < 500
            })

        near_boundary = [b for b in boundary_issues if b['near_boundary']]
        print(f"Duplicates near boundary (<500ms): {len(near_boundary)} / {len(boundary_issues)} ({len(near_boundary)/len(boundary_issues)*100:.1f}%)")

        if len(near_boundary) / len(boundary_issues) > 0.5:
            print(f"✅ HYPOTHESIS H2.2 VALIDATED: Duplicates correlate with boundaries")
        else:
            print(f"❌ HYPOTHESIS H2.2 REJECTED: No strong correlation with boundaries")
    else:
        print(f"⚠️  HYPOTHESIS H2.2: No duplicates to analyze")

    # H2.3: Check if high-frequency periods have more duplicates
    print("\n--- H2.3: High Frequency Correlation ---")
    if all_trades:
        # Group trades by symbol and 10-second windows
        windows = defaultdict(list)
        for trade in all_trades:
            window = (int(trade['received_at']) // 10) * 10
            windows[f"{trade['symbol']}_{window}"].append(trade)

        # Calculate frequency and duplication rate per window
        window_stats = []
        for window_key, trades_in_window in windows.items():
            signatures = [t['signature'] for t in trades_in_window]
            duplicates_in_window = len(signatures) - len(set(signatures))
            frequency = len(trades_in_window)

            if frequency > 0:
                window_stats.append({
                    'window': window_key,
                    'frequency': frequency,
                    'duplicates': duplicates_in_window,
                    'dup_rate': duplicates_in_window / frequency
                })

        if window_stats:
            # Sort by frequency
            window_stats.sort(key=lambda x: x['frequency'], reverse=True)

            print(f"Total windows analyzed: {len(window_stats)}")
            print(f"\nTop 5 highest frequency windows:")
            for i, ws in enumerate(window_stats[:5]):
                print(f"  {i+1}. Freq={ws['frequency']}, Dups={ws['duplicates']}, Rate={ws['dup_rate']*100:.1f}%")

            # Check correlation
            high_freq_windows = [w for w in window_stats if w['frequency'] > 10]
            if high_freq_windows:
                avg_dup_rate_high_freq = sum(w['dup_rate'] for w in high_freq_windows) / len(high_freq_windows)
                low_freq_windows = [w for w in window_stats if w['frequency'] <= 10]
                avg_dup_rate_low_freq = sum(w['dup_rate'] for w in low_freq_windows) / len(low_freq_windows) if low_freq_windows else 0

                print(f"\nAverage duplication rate:")
                print(f"  High frequency (>10 trades/10s): {avg_dup_rate_high_freq*100:.2f}%")
                print(f"  Low frequency (<=10 trades/10s): {avg_dup_rate_low_freq*100:.2f}%")

                if avg_dup_rate_high_freq > avg_dup_rate_low_freq * 1.5:
                    print(f"✅ HYPOTHESIS H2.3 VALIDATED: Higher duplication in high-frequency periods")
                else:
                    print(f"❌ HYPOTHESIS H2.3 REJECTED: No strong correlation with frequency")

    # Group duplicates by symbol
    print("\n--- Per-Symbol Analysis ---")
    by_symbol = defaultdict(list)
    for trade in all_trades:
        by_symbol[trade['symbol']].append(trade)

    for symbol, trades in by_symbol.items():
        signatures = [t['signature'] for t in trades]
        unique = len(set(signatures))
        duplicates = len(signatures) - unique
        print(f"{symbol}: {len(trades)} trades, {unique} unique, {duplicates} duplicates ({duplicates/len(trades)*100:.2f}%)")


async def test_volume_impact():
    """
    H2.5: Test if duplicates affect OHLCV correctness
    """
    print("\n=== CROSS-AUDIT #2.2: Volume Impact Analysis ===\n")

    test_coins = ['10000LADYSUSDT']
    aggregator = TradeWebSocket(test_coins)

    # Track candles and check for duplicates in underlying trades
    candle_data = []
    trade_tracking = defaultdict(list)

    # Monitor trades going into intervals
    original_process = aggregator._process_trade_to_candle

    async def monitored_process(symbol: str, trade_data: Dict):
        interval = (trade_data['timestamp'] // 10000) * 10000
        signature = f"{trade_data['timestamp']}_{trade_data['price']}_{trade_data['size']}"

        trade_tracking[f"{symbol}_{interval}"].append({
            'signature': signature,
            'volume': trade_data['size']
        })

        await original_process(symbol, trade_data)

    aggregator._process_trade_to_candle = monitored_process

    # Monitor candle creation
    async def monitor_candles():
        last_count = 0
        while aggregator.running:
            for coin in test_coins:
                current_count = len(aggregator.candles_buffer.get(coin, []))
                if current_count > last_count:
                    candles = aggregator.candles_buffer[coin]
                    new_candles = candles[last_count:]
                    for candle in new_candles:
                        candle_data.append({
                            'coin': coin,
                            'timestamp': candle['timestamp'],
                            'volume': candle['volume'],
                            'ohlc': [candle['open'], candle['high'], candle['low'], candle['close']]
                        })
                    last_count = current_count
            await asyncio.sleep(1)

    ws_task = asyncio.create_task(aggregator.start_connection())
    monitor_task = asyncio.create_task(monitor_candles())

    print(f"Monitoring for 60 seconds...")
    await asyncio.sleep(60)

    await aggregator.stop()
    await ws_task
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass

    # ANALYSIS
    print(f"\n📊 Candles created: {len(candle_data)}")

    # Check each candle for duplicates in trades
    print("\n--- H2.5: Volume Inflation Analysis ---")
    volume_inflation_cases = []

    for candle in candle_data:
        interval_key = f"{candle['coin']}_{candle['timestamp']}"
        trades = trade_tracking.get(interval_key, [])

        if trades:
            signatures = [t['signature'] for t in trades]
            unique_signatures = set(signatures)

            if len(signatures) != len(unique_signatures):
                # Found duplicates
                duplicate_count = len(signatures) - len(unique_signatures)
                total_volume = sum(t['volume'] for t in trades)
                unique_volumes = {}
                for t in trades:
                    if t['signature'] not in unique_volumes:
                        unique_volumes[t['signature']] = t['volume']
                correct_volume = sum(unique_volumes.values())

                volume_inflation_cases.append({
                    'candle': candle['timestamp'],
                    'reported_volume': candle['volume'],
                    'calculated_volume': total_volume,
                    'correct_volume': correct_volume,
                    'inflation': total_volume - correct_volume,
                    'inflation_pct': (total_volume - correct_volume) / correct_volume * 100 if correct_volume > 0 else 0,
                    'duplicate_count': duplicate_count
                })

    if volume_inflation_cases:
        print(f"✅ HYPOTHESIS H2.5 VALIDATED: Duplicates inflate volume")
        print(f"Cases found: {len(volume_inflation_cases)}")

        for i, case in enumerate(volume_inflation_cases[:5]):
            print(f"\n  Case {i+1}:")
            print(f"    Timestamp: {case['candle']}")
            print(f"    Reported volume: {case['reported_volume']:.2f}")
            print(f"    Correct volume: {case['correct_volume']:.2f}")
            print(f"    Inflation: +{case['inflation']:.2f} (+{case['inflation_pct']:.1f}%)")
            print(f"    Duplicate trades: {case['duplicate_count']}")
    else:
        print(f"❌ HYPOTHESIS H2.5: No volume inflation detected (or no duplicates in test period)")


async def main():
    print("="*60)
    print("CROSS-AUDIT #2 - TRADE DUPLICATION DEEP DIVE")
    print("="*60)

    try:
        await test_duplication_patterns()
        await asyncio.sleep(2)

        await test_volume_impact()

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during tests: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("CROSS-AUDIT #2 COMPLETED")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())