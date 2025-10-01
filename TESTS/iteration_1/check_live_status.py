"""
Check current live status of running system
"""
import asyncio
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.websocket_handler import TradeWebSocket
from src.trading_api import get_all_symbols_by_volume

async def check_status():
    """Quick status check"""
    print("\n" + "="*80)
    print("LIVE STATUS CHECK")
    print("="*80)

    # Get filtered coins
    filtered_coins = get_all_symbols_by_volume()
    print(f"\n📊 Filtered coins: {len(filtered_coins)}")

    # Create aggregator
    aggregator = TradeWebSocket(filtered_coins)

    # Start WebSocket
    ws_task = asyncio.create_task(aggregator.start_connection())

    # Wait for data
    print("\n⏳ Waiting 30 seconds for data...")
    await asyncio.sleep(30)

    # Check status
    print("\n📊 Current status:")

    candle_counts = []
    for coin in filtered_coins[:10]:  # Check first 10 coins
        signal, signal_info = aggregator.get_signal_data(coin)
        if signal_info:
            candle_count = signal_info.get('candle_count', 0)
            candle_counts.append(candle_count)

            criteria = signal_info.get('criteria', {})
            validation_error = criteria.get('validation_error', '')

            status = f"Candles: {candle_count:3d}"
            if validation_error:
                status += f" | {validation_error}"

            print(f"   {coin:15s} {status}")

    if candle_counts:
        min_candles = min(candle_counts)
        max_candles = max(candle_counts)
        avg_candles = sum(candle_counts) / len(candle_counts)

        print(f"\n📊 Candle stats (n={len(candle_counts)}):")
        print(f"   Min: {min_candles} | Max: {max_candles} | Avg: {avg_candles:.1f}")

        if min_candles >= 70:
            print(f"\n✅ WARMUP COMPLETE (min candles: {min_candles})")

            # Check if any signals would be logged
            print(f"\n📊 Checking signal logging conditions...")

            for coin in filtered_coins[:5]:
                signal, signal_info = aggregator.get_signal_data(coin)

                # Simulate log_signal conditions
                has_validation_error = False
                if signal_info and 'criteria' in signal_info:
                    validation_error = signal_info['criteria'].get('validation_error', '')
                    if validation_error:
                        has_validation_error = True

                log_status = "✅ WILL LOG" if not has_validation_error else f"❌ SKIPPED ({validation_error})"
                signal_status = "TRUE" if signal else "FALSE"

                print(f"   {coin:15s} signal={signal_status:5s} | {log_status}")
        else:
            print(f"\n⏳ Still warming up: {min_candles}/70 candles")

    await aggregator.stop()
    print("\n" + "="*80)

if __name__ == "__main__":
    asyncio.run(check_status())
