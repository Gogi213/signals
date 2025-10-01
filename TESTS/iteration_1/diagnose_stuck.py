"""
Diagnose why signals.json stopped updating
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
from src.config import WARMUP_INTERVALS

async def diagnose():
    """Diagnose current state"""
    print("\n" + "="*80)
    print("DIAGNOSTIC TEST")
    print("="*80)

    filtered_coins = get_all_symbols_by_volume()

    print(f"\n📊 Filtered coins: {len(filtered_coins)}")
    print(f"   First 5: {', '.join(filtered_coins[:5])}")
    print(f"   WARMUP_INTERVALS: {WARMUP_INTERVALS}")

    # Create aggregator (reads existing websocket.json state)
    aggregator = TradeWebSocket(filtered_coins)

    # Start websocket to get current state
    ws_task = asyncio.create_task(aggregator.start_connection())

    print("\n⏳ Waiting 5 seconds for data...")
    await asyncio.sleep(5)

    print("\n📊 Checking signal state for first 10 coins:")

    warmup_active = False
    min_candles = float('inf')

    for i, coin in enumerate(filtered_coins[:10]):
        signal, signal_info = aggregator.get_signal_data(coin)

        if signal_info:
            candle_count = signal_info.get('candle_count', 0)
            criteria = signal_info.get('criteria', {})
            validation_error = criteria.get('validation_error', '')

            # Check warmup
            if validation_error.startswith('Warmup:'):
                warmup_active = True
                min_candles = min(min_candles, candle_count)

            print(f"\n   [{i+1}] {coin}")
            print(f"       Candles: {candle_count}")
            print(f"       Signal: {signal}")
            print(f"       Validation error: '{validation_error}'")

            if 'criteria_details' in criteria:
                details = criteria['criteria_details']
                if details:
                    print(f"       Criteria details present: {len(details)} items")
        else:
            print(f"\n   [{i+1}] {coin} - NO signal_info")

    print(f"\n📊 Warmup status:")
    print(f"   warmup_active: {warmup_active}")
    print(f"   min_candles: {min_candles}")

    if not warmup_active:
        print(f"   ✅ WARMUP COMPLETE (should be logging signals)")
    else:
        print(f"   ⏳ WARMUP IN PROGRESS ({min_candles}/{WARMUP_INTERVALS})")

    await aggregator.stop()
    print("\n" + "="*80)

if __name__ == "__main__":
    asyncio.run(diagnose())
