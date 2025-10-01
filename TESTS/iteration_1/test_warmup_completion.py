"""
Test warmup completion and signal logging
"""
import asyncio
import sys
import io
import json
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.websocket_handler import TradeWebSocket
from src.trading_api import get_all_symbols_by_volume
from src.config import start_candle_logging, WARMUP_INTERVALS

async def test_warmup():
    """Test warmup completion logic"""
    print("\n" + "="*80)
    print(f"WARMUP TEST (WARMUP_INTERVALS={WARMUP_INTERVALS})")
    print("="*80)

    filtered_coins = get_all_symbols_by_volume()
    test_coins = filtered_coins[:3]

    print(f"\n📊 Testing with {len(test_coins)} coins: {', '.join(test_coins)}")

    start_candle_logging()
    await asyncio.sleep(0.5)

    aggregator = TradeWebSocket(test_coins)
    ws_task = asyncio.create_task(aggregator.start_connection())

    print("\n⏳ Monitoring warmup...")

    warmup_complete_flag = False
    iterations = 0

    try:
        for i in range(600):  # 600 * 0.3s = 180s
            await asyncio.sleep(0.3)
            iterations += 1

            # Check warmup status for all coins
            warmup_active = False
            min_candles = float('inf')
            coin_signals = {}

            for coin in test_coins:
                signal, signal_info = aggregator.get_signal_data(coin)
                coin_signals[coin] = (signal, signal_info)

                if signal_info and 'criteria' in signal_info:
                    criteria = signal_info['criteria']
                    if criteria.get('validation_error', '').startswith('Warmup:'):
                        warmup_active = True
                        candle_count = signal_info.get('candle_count', 0)
                        min_candles = min(min_candles, candle_count)

            # Check if warmup complete
            if not warmup_active and not warmup_complete_flag:
                warmup_complete_flag = True
                print(f"\n✅ WARMUP COMPLETE at iteration {iterations}")
                print(f"   Min candles: {min_candles}")

                # Try logging signals with warmup_complete=True
                from src.config import log_signal
                for coin, (signal, signal_info) in coin_signals.items():
                    print(f"\n   Attempting to log signal for {coin}:")
                    print(f"     - signal: {signal}")
                    print(f"     - candle_count: {signal_info.get('candle_count', 0)}")

                    if signal_info and 'criteria' in signal_info:
                        criteria = signal_info['criteria']
                        val_err_root = signal_info.get('validation_error', '')
                        val_err_criteria = criteria.get('validation_error', '')
                        print(f"     - validation_error (root): '{val_err_root}'")
                        print(f"     - validation_error (criteria): '{val_err_criteria}'")

                    log_signal(coin, signal, signal_info, warmup_complete=True)
                    print(f"     ✅ log_signal() called")

                break

            if i % 30 == 0 and warmup_active:
                print(f"   [{i*0.3:.0f}s] Warmup: {min_candles}/{WARMUP_INTERVALS} candles")

    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
    finally:
        await aggregator.stop()
        await asyncio.sleep(1)

    # Check if signals.json was created
    signals_log = project_root / 'logs' / 'signals.json'
    if signals_log.exists():
        print(f"\n✅ signals.json CREATED")
        with open(signals_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            print(f"   Entries: {len(lines)}")
            if lines:
                print(f"\n   First entry:")
                data = json.loads(lines[0])
                print(f"     Coin: {data.get('coin')}")
                print(f"     Signal: {data.get('signal_type')}")
    else:
        print(f"\n❌ signals.json NOT CREATED")

    print("\n" + "="*80)

if __name__ == "__main__":
    asyncio.run(test_warmup())
