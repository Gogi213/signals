"""
CROSS-AUDIT #5 - Final Validation
Final comprehensive test with proper coin selection

FINAL HYPOTHESES:
H5.1: Дубликация составляет стабильно ~9-14% от всех трейдов
H5.2: Volume inflation от дубликатов можно измерить на реальных данных
H5.3: Система работает стабильно 300+ секунд без критических проблем
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


async def final_comprehensive_test():
    """
    Final validation of all key findings
    """
    print("\n=== CROSS-AUDIT #5: Final Comprehensive Test ===\n")

    # Use allowed active coins (not in blacklist)
    test_coins = ['ARBUSDT', '1000PEPEUSDT', 'AVAXUSDT', 'LINKUSDT', 'APTUSDT']

    aggregator = TradeWebSocket(test_coins)

    # Comprehensive tracking
    stats = {
        'start_time': time.time(),
        'trades': {
            'total': 0,
            'by_coin': {coin: 0 for coin in test_coins},
            'duplicates': 0,
            'duplicate_examples': []
        },
        'candles': {
            'total': 0,
            'by_coin': {coin: [] for coin in test_coins},
            'with_volume': 0,
            'forward_fill': 0
        },
        'signals': {
            'checks': 0,
            'changes': 0,
            'true_count': 0
        }
    }

    # Track duplicates
    seen_trades = {}

    original_process = aggregator._process_trade_to_candle

    async def comprehensive_track(symbol: str, trade_data: Dict):
        sig = f"{symbol}_{trade_data['timestamp']}_{trade_data['price']}_{trade_data['size']}"

        # Check for duplicate
        if sig in seen_trades:
            stats['trades']['duplicates'] += 1
            if len(stats['trades']['duplicate_examples']) < 10:
                stats['trades']['duplicate_examples'].append({
                    'sig': sig,
                    'first_seen': seen_trades[sig],
                    'duplicate_at': time.time()
                })
        else:
            seen_trades[sig] = time.time()

        stats['trades']['total'] += 1
        stats['trades']['by_coin'][symbol] += 1

        await original_process(symbol, trade_data)

    aggregator._process_trade_to_candle = comprehensive_track

    # Monitor candles
    async def monitor_candles():
        last_counts = {coin: 0 for coin in test_coins}

        while aggregator.running:
            for coin in test_coins:
                candles = aggregator.candles_buffer.get(coin, [])
                current_count = len(candles)

                if current_count > last_counts[coin]:
                    new_candles = candles[last_counts[coin]:]
                    for candle in new_candles:
                        stats['candles']['total'] += 1
                        stats['candles']['by_coin'][coin].append(candle)

                        if candle['volume'] > 0:
                            stats['candles']['with_volume'] += 1
                        else:
                            stats['candles']['forward_fill'] += 1

                    last_counts[coin] = current_count

            await asyncio.sleep(1)

    # Monitor signals
    async def monitor_signals():
        last_signals = {coin: None for coin in test_coins}

        while aggregator.running:
            for coin in test_coins:
                signal, signal_info = aggregator.get_signal_data(coin)
                stats['signals']['checks'] += 1

                if last_signals[coin] is None or last_signals[coin] != signal:
                    stats['signals']['changes'] += 1
                    if signal:
                        stats['signals']['true_count'] += 1

                last_signals[coin] = signal

            await asyncio.sleep(10)

    # Start everything
    ws_task = asyncio.create_task(aggregator.start_connection())
    candle_task = asyncio.create_task(monitor_candles())
    signal_task = asyncio.create_task(monitor_signals())

    print(f"Running comprehensive test for 300 seconds (5 minutes)...")
    print(f"Coins: {', '.join(test_coins)}\n")

    # Progress updates
    for i in range(30):
        await asyncio.sleep(10)
        elapsed = time.time() - stats['start_time']
        print(f"[{elapsed:.0f}s] Trades: {stats['trades']['total']}, "
              f"Dups: {stats['trades']['duplicates']} ({stats['trades']['duplicates']/stats['trades']['total']*100:.1f}%), "
              f"Candles: {stats['candles']['total']}")

    # Stop
    await aggregator.stop()
    await ws_task
    candle_task.cancel()
    signal_task.cancel()
    try:
        await candle_task
    except asyncio.CancelledError:
        pass
    try:
        await signal_task
    except asyncio.CancelledError:
        pass

    # FINAL ANALYSIS
    print(f"\n{'='*60}")
    print("FINAL RESULTS")
    print(f"{'='*60}\n")

    duration = time.time() - stats['start_time']
    print(f"Duration: {duration:.1f}s")

    # H5.1: Duplication rate
    print(f"\n--- H5.1: Duplication Rate ---")
    dup_rate = stats['trades']['duplicates'] / stats['trades']['total'] * 100 if stats['trades']['total'] > 0 else 0
    print(f"Total trades: {stats['trades']['total']}")
    print(f"Duplicates: {stats['trades']['duplicates']} ({dup_rate:.2f}%)")

    if 8 <= dup_rate <= 16:
        print(f"✅ HYPOTHESIS H5.1 VALIDATED: Duplication rate is ~9-14% (actual: {dup_rate:.2f}%)")
    else:
        print(f"⚠️  HYPOTHESIS H5.1: Rate outside expected range (actual: {dup_rate:.2f}%)")

    print(f"\nDuplication by coin:")
    for coin in test_coins:
        coin_trades = stats['trades']['by_coin'][coin]
        if coin_trades > 0:
            print(f"  {coin}: {coin_trades} trades")

    # H5.2: Volume analysis
    print(f"\n--- H5.2: Volume Analysis ---")
    print(f"Total candles created: {stats['candles']['total']}")
    print(f"  With volume: {stats['candles']['with_volume']}")
    print(f"  Forward-fill (0 volume): {stats['candles']['forward_fill']}")

    # Calculate average volumes per coin
    print(f"\nAverage volumes by coin:")
    for coin, candles in stats['candles']['by_coin'].items():
        if candles:
            volumes = [c['volume'] for c in candles if c['volume'] > 0]
            if volumes:
                avg_vol = sum(volumes) / len(volumes)
                print(f"  {coin}: {avg_vol:.2f} (from {len(volumes)} candles)")

    if stats['candles']['with_volume'] > 20:
        print(f"✅ HYPOTHESIS H5.2: Volume data collected successfully")
    else:
        print(f"⚠️  HYPOTHESIS H5.2: Insufficient volume data")

    # H5.3: System stability
    print(f"\n--- H5.3: System Stability ---")
    print(f"Signal checks: {stats['signals']['checks']}")
    print(f"Signal changes: {stats['signals']['changes']}")
    print(f"True signals: {stats['signals']['true_count']}")

    avg_trades_per_sec = stats['trades']['total'] / duration
    print(f"\nPerformance:")
    print(f"  Trades/second: {avg_trades_per_sec:.2f}")
    print(f"  Candles/coin: {stats['candles']['total'] / len(test_coins):.1f}")

    if stats['candles']['total'] > 50 and stats['trades']['total'] > 100:
        print(f"✅ HYPOTHESIS H5.3 VALIDATED: System is stable for 300+ seconds")
    else:
        print(f"❌ HYPOTHESIS H5.3 REJECTED: System did not process enough data")

    # Summary
    print(f"\n{'='*60}")
    print("KEY FINDINGS SUMMARY")
    print(f"{'='*60}")
    print(f"1. Duplication Rate: {dup_rate:.2f}% (expected ~9-14%)")
    print(f"2. Total Data Processed: {stats['trades']['total']} trades → {stats['candles']['total']} candles")
    print(f"3. System Stability: {'STABLE' if stats['candles']['total'] > 50 else 'INSUFFICIENT DATA'}")
    ff_pct = (stats['candles']['forward_fill']/stats['candles']['total']*100) if stats['candles']['total'] > 0 else 0
    print(f"4. Forward-fill Candles: {stats['candles']['forward_fill']} ({ff_pct:.1f}%)")


async def main():
    print("="*60)
    print("CROSS-AUDIT #5 - FINAL VALIDATION")
    print("="*60)

    try:
        await final_comprehensive_test()

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("FINAL AUDIT COMPLETED")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())