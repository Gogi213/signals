"""
CROSS-AUDIT #4.2 - Deduplication Impact Only (Shortened)
Focused test on H4.2 and H4.3 with shorter duration
"""
import asyncio
import time
from typing import Dict
import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.websocket_handler import TradeWebSocket


async def test_deduplication_impact():
    """
    H4.2, H4.3: Measure deduplication impact
    """
    print("\n=== CROSS-AUDIT #4.2: Deduplication Impact ===\n")

    # Use very active coins
    test_coins = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']

    # Test 1: WITH duplicates
    print("--- Phase 1: WITH duplicates (180s) ---")
    aggregator_dup = TradeWebSocket(test_coins)

    dup_stats = {
        'candles': [],
        'signals': [],
        'true_signals': 0,
        'duplicate_count': 0,
        'total_trades': 0
    }

    seen_trades_dup = set()
    original_dup = aggregator_dup._process_trade_to_candle

    async def track_dup(symbol: str, trade_data: Dict):
        sig = f"{symbol}_{trade_data['timestamp']}_{trade_data['price']}_{trade_data['size']}"
        if sig in seen_trades_dup:
            dup_stats['duplicate_count'] += 1
        seen_trades_dup.add(sig)
        dup_stats['total_trades'] += 1
        await original_dup(symbol, trade_data)

    aggregator_dup._process_trade_to_candle = track_dup

    async def monitor_dup():
        checks = 0
        while aggregator_dup.running and checks < 18:  # 18 checks over 180s
            for coin in test_coins:
                candles = aggregator_dup.candles_buffer.get(coin, [])
                if len(candles) >= 20:  # Reduced warmup for faster test
                    signal, signal_info = aggregator_dup.get_signal_data(coin)

                    if candles and candles[-1]['volume'] > 0:
                        last_candle = candles[-1]
                        dup_stats['candles'].append({
                            'coin': coin,
                            'volume': last_candle['volume'],
                            'timestamp': last_candle['timestamp']
                        })

                        dup_stats['signals'].append({
                            'coin': coin,
                            'signal': signal
                        })

                        if signal:
                            dup_stats['true_signals'] += 1

            checks += 1
            await asyncio.sleep(10)

    ws_task_dup = asyncio.create_task(aggregator_dup.start_connection())
    monitor_task_dup = asyncio.create_task(monitor_dup())

    print(f"Running for 180 seconds...")
    await asyncio.sleep(180)

    await aggregator_dup.stop()
    await ws_task_dup
    monitor_task_dup.cancel()
    try:
        await monitor_task_dup
    except asyncio.CancelledError:
        pass

    print(f"\nPhase 1 Results:")
    print(f"  Total trades: {dup_stats['total_trades']}")
    print(f"  Duplicates: {dup_stats['duplicate_count']} ({dup_stats['duplicate_count']/dup_stats['total_trades']*100:.2f}% if dup_stats['total_trades'] > 0 else 0)")
    print(f"  Candles tracked: {len(dup_stats['candles'])}")
    print(f"  Signals checked: {len(dup_stats['signals'])}")
    print(f"  True signals: {dup_stats['true_signals']}")

    # Test 2: WITHOUT duplicates
    print("\n--- Phase 2: WITHOUT duplicates (180s) ---")
    aggregator_nodup = TradeWebSocket(test_coins)

    nodup_stats = {
        'candles': [],
        'signals': [],
        'true_signals': 0,
        'filtered_count': 0,
        'total_trades': 0
    }

    seen_trades_nodup = set()
    original_nodup = aggregator_nodup._process_trade_to_candle

    async def dedup_track(symbol: str, trade_data: Dict):
        sig = f"{symbol}_{trade_data['timestamp']}_{trade_data['price']}_{trade_data['size']}"

        if sig in seen_trades_nodup:
            nodup_stats['filtered_count'] += 1
            return

        seen_trades_nodup.add(sig)
        nodup_stats['total_trades'] += 1
        await original_nodup(symbol, trade_data)

    aggregator_nodup._process_trade_to_candle = dedup_track

    async def monitor_nodup():
        checks = 0
        while aggregator_nodup.running and checks < 18:
            for coin in test_coins:
                candles = aggregator_nodup.candles_buffer.get(coin, [])
                if len(candles) >= 20:
                    signal, signal_info = aggregator_nodup.get_signal_data(coin)

                    if candles and candles[-1]['volume'] > 0:
                        last_candle = candles[-1]
                        nodup_stats['candles'].append({
                            'coin': coin,
                            'volume': last_candle['volume'],
                            'timestamp': last_candle['timestamp']
                        })

                        nodup_stats['signals'].append({
                            'coin': coin,
                            'signal': signal
                        })

                        if signal:
                            nodup_stats['true_signals'] += 1

            checks += 1
            await asyncio.sleep(10)

    ws_task_nodup = asyncio.create_task(aggregator_nodup.start_connection())
    monitor_task_nodup = asyncio.create_task(monitor_nodup())

    print(f"Running for 180 seconds...")
    await asyncio.sleep(180)

    await aggregator_nodup.stop()
    await ws_task_nodup
    monitor_task_nodup.cancel()
    try:
        await monitor_task_nodup
    except asyncio.CancelledError:
        pass

    print(f"\nPhase 2 Results:")
    print(f"  Trades processed: {nodup_stats['total_trades']}")
    print(f"  Filtered duplicates: {nodup_stats['filtered_count']}")
    print(f"  Candles tracked: {len(nodup_stats['candles'])}")
    print(f"  Signals checked: {len(nodup_stats['signals'])}")
    print(f"  True signals: {nodup_stats['true_signals']}")

    # COMPARISON
    print("\n--- H4.2 & H4.3: Impact Analysis ---")

    if dup_stats['candles'] and nodup_stats['candles']:
        # H4.2: Volume comparison
        dup_volumes = [c['volume'] for c in dup_stats['candles']]
        nodup_volumes = [c['volume'] for c in nodup_stats['candles']]

        if dup_volumes and nodup_volumes:
            avg_dup = sum(dup_volumes) / len(dup_volumes)
            avg_nodup = sum(nodup_volumes) / len(nodup_volumes)
            volume_diff_pct = (avg_dup - avg_nodup) / avg_nodup * 100 if avg_nodup > 0 else 0

            print(f"\nH4.2: Volume Impact")
            print(f"  WITH duplicates avg volume: {avg_dup:.2f}")
            print(f"  WITHOUT duplicates avg volume: {avg_nodup:.2f}")
            print(f"  Volume inflation: {volume_diff_pct:.2f}%")
            expected_inflation = (dup_stats['duplicate_count']/dup_stats['total_trades']*100) if dup_stats['total_trades'] > 0 else 0
            print(f"  Expected inflation: ~{expected_inflation:.2f}%")

            if abs(volume_diff_pct - expected_inflation) < 3 and volume_diff_pct > 0:
                print(f"✅ HYPOTHESIS H4.2 VALIDATED: Volume inflation matches duplicate rate")
            elif volume_diff_pct > 5:
                print(f"⚠️  HYPOTHESIS H4.2: Volume inflation detected but doesn't match duplicate rate")
            else:
                print(f"❌ HYPOTHESIS H4.2 REJECTED: Minimal volume inflation")

        # H4.3: Signal impact
        print(f"\nH4.3: Signal Impact")
        print(f"  WITH duplicates true signals: {dup_stats['true_signals']}")
        print(f"  WITHOUT duplicates true signals: {nodup_stats['true_signals']}")

        if dup_stats['signals'] and nodup_stats['signals']:
            rate_dup = dup_stats['true_signals'] / len(dup_stats['signals']) * 100
            rate_nodup = nodup_stats['true_signals'] / len(nodup_stats['signals']) * 100

            print(f"  WITH duplicates rate: {rate_dup:.2f}%")
            print(f"  WITHOUT duplicates rate: {rate_nodup:.2f}%")
            print(f"  Difference: {abs(rate_dup - rate_nodup):.2f}%")

            if abs(rate_dup - rate_nodup) > 5:
                print(f"✅ HYPOTHESIS H4.3 VALIDATED: Deduplication significantly affects signals (>5% diff)")
            else:
                print(f"❌ HYPOTHESIS H4.3 REJECTED: Minimal impact on signals (<5% diff)")
    else:
        print(f"⚠️  Insufficient data for comparison")
        print(f"  WITH dup candles: {len(dup_stats['candles'])}, signals: {len(dup_stats['signals'])}")
        print(f"  WITHOUT dup candles: {len(nodup_stats['candles'])}, signals: {len(nodup_stats['signals'])}")


async def main():
    print("="*60)
    print("CROSS-AUDIT #4.2 - DEDUPLICATION IMPACT TEST")
    print("="*60)

    try:
        await test_deduplication_impact()

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("TEST COMPLETED")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())