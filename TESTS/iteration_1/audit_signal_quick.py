"""
Quick signal audit - modifies WARMUP_INTERVALS to 25 for faster testing
"""
import asyncio
import sys
import io
import json
from pathlib import Path

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# PATCH: Override WARMUP_INTERVALS before imports
import src.config
src.config.WARMUP_INTERVALS = 25  # Reduced from 70 for quick testing
from src.config import WARMUP_INTERVALS

from src.websocket_handler import TradeWebSocket
from src.trading_api import get_all_symbols_by_volume
from src.config import start_candle_logging

async def audit_signal_generation():
    """Audit signal generation with reduced warmup"""
    print("\n" + "="*80)
    print("QUICK SIGNAL AUDIT (WARMUP=25)")
    print("="*80)

    # Get filtered coins
    filtered_coins = get_all_symbols_by_volume()
    test_coins = filtered_coins[:3]  # Test with 3 coins

    print(f"\n📊 Testing with {len(test_coins)} coins: {', '.join(test_coins)}")
    print(f"📊 Warmup intervals: {WARMUP_INTERVALS} (~{WARMUP_INTERVALS * 10}s)")

    # Start async candle logging worker
    start_candle_logging()
    await asyncio.sleep(0.5)

    # Create aggregator
    aggregator = TradeWebSocket(test_coins)

    # Start WebSocket
    ws_task = asyncio.create_task(aggregator.start_connection())

    print("\n⏳ Running audit...")

    # Track state
    warmup_complete = False
    signal_checks = []
    last_log = 0

    try:
        for iteration in range(1000):  # ~300 seconds
            await asyncio.sleep(0.3)

            # Check all coins
            min_candles = float('inf')
            warmup_active = False

            for coin in test_coins:
                signal, signal_info = aggregator.get_signal_data(coin)

                if signal_info and 'criteria' in signal_info:
                    criteria = signal_info['criteria']
                    candle_count = signal_info.get('candle_count', 0)
                    min_candles = min(min_candles, candle_count)

                    # Check warmup status
                    validation_error = criteria.get('validation_error', '')
                    if validation_error.startswith('Warmup:'):
                        warmup_active = True

                    # Record all checks
                    signal_checks.append({
                        'coin': coin,
                        'signal': signal,
                        'candle_count': candle_count,
                        'validation_error': validation_error,
                        'warmup_active': warmup_active,
                        'criteria': criteria
                    })

            # Log warmup progress
            if warmup_active and min_candles != float('inf'):
                if min_candles - last_log >= 5:
                    print(f"   🔥 Warmup: {min_candles}/{WARMUP_INTERVALS} candles")
                    last_log = min_candles

            # Mark warmup complete
            if not warmup_active and not warmup_complete:
                warmup_complete = True
                print(f"\n✅ WARMUP COMPLETE at {min_candles} candles")
                print(f"   Collecting 30 post-warmup checks...\n")

            # Stop after collecting enough post-warmup data
            post_warmup = [c for c in signal_checks if not c['warmup_active']]
            if warmup_complete and len(post_warmup) >= 30:
                print(f"✅ Collected {len(post_warmup)} post-warmup checks")
                break

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted")
    finally:
        await aggregator.stop()
        await asyncio.sleep(1)

    # Analyze
    print("\n" + "="*80)
    print("SIGNAL ANALYSIS")
    print("="*80)

    if not signal_checks:
        print("\n❌ NO DATA COLLECTED")
        return

    post_warmup = [c for c in signal_checks if not c['warmup_active']]

    print(f"\n📊 Total checks: {len(signal_checks)}")
    print(f"📊 Post-warmup checks: {len(post_warmup)}")

    if not post_warmup:
        print("\n❌ WARMUP NOT COMPLETED")
        return

    # Analyze by coin
    by_coin = {}
    for check in post_warmup:
        coin = check['coin']
        if coin not in by_coin:
            by_coin[coin] = {'true': 0, 'false': 0, 'errors': set()}

        if check['signal']:
            by_coin[coin]['true'] += 1
        else:
            by_coin[coin]['false'] += 1

        if check['validation_error']:
            by_coin[coin]['errors'].add(check['validation_error'])

    print(f"\n📊 Signals by coin:")
    for coin, stats in by_coin.items():
        err_str = f" | Errors: {list(stats['errors'])}" if stats['errors'] else ""
        print(f"   {coin:15s} TRUE:{stats['true']:3d} FALSE:{stats['false']:3d}{err_str}")

    # Show sample FALSE signals with criteria
    false_checks = [c for c in post_warmup if not c['signal']]
    if false_checks:
        print(f"\n📊 Sample FALSE signals (showing 5/{len(false_checks)}):")
        for i, check in enumerate(false_checks[:5]):
            coin = check['coin']
            criteria = check['criteria']
            print(f"\n   [{i+1}] {coin} (candles: {check['candle_count']})")

            if 'criteria_details' in criteria:
                details = criteria['criteria_details']
                for name, data in details.items():
                    passed = "✅" if data.get('passed') else "❌"
                    curr = data.get('current', 'N/A')
                    thresh = data.get('threshold', 'N/A')
                    print(f"       {passed} {name:15s} curr:{curr:10} thresh:{thresh}")

    # Show TRUE signals
    true_checks = [c for c in post_warmup if c['signal']]
    if true_checks:
        print(f"\n📊 TRUE signals found: {len(true_checks)}")
        for i, check in enumerate(true_checks[:3]):
            coin = check['coin']
            criteria = check['criteria']
            print(f"\n   [{i+1}] {coin} (candles: {check['candle_count']})")

            if 'criteria_details' in criteria:
                details = criteria['criteria_details']
                for name, data in details.items():
                    passed = "✅" if data.get('passed') else "❌"
                    curr = data.get('current', 'N/A')
                    thresh = data.get('threshold', 'N/A')
                    print(f"       {passed} {name:15s} curr:{curr:10} thresh:{thresh}")
    else:
        print(f"\n❌ NO TRUE SIGNALS in {len(post_warmup)} checks")

    print("\n" + "="*80)

if __name__ == "__main__":
    asyncio.run(audit_signal_generation())
