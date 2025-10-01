"""
Audit signal generation to understand why no signals are being generated
"""
import asyncio
import sys
import io
import json
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.websocket_handler import TradeWebSocket
from src.trading_api import get_all_symbols_by_volume
from src.config import start_candle_logging, WARMUP_INTERVALS

async def audit_signal_generation():
    """Audit signal generation process"""
    print("\n" + "="*80)
    print("SIGNAL GENERATION AUDIT")
    print("="*80)

    # Get filtered coins
    filtered_coins = get_all_symbols_by_volume()
    test_coins = filtered_coins[:5]  # Test with 5 coins

    print(f"\n📊 Testing with {len(test_coins)} coins: {', '.join(test_coins)}")
    print(f"📊 Warmup intervals required: {WARMUP_INTERVALS}")

    # Start async candle logging worker
    start_candle_logging()
    await asyncio.sleep(0.5)

    # Create aggregator
    aggregator = TradeWebSocket(test_coins)

    # Start WebSocket
    ws_task = asyncio.create_task(aggregator.start_connection())

    print("\n⏳ Waiting for warmup + signals...")

    # Track state
    warmup_complete = False
    signal_checks = []

    try:
        for iteration in range(500):  # Run for ~150 seconds (500 * 0.3s)
            await asyncio.sleep(0.3)

            # Check warmup status
            min_candles = float('inf')
            warmup_active = False

            for coin in test_coins:
                signal, signal_info = aggregator.get_signal_data(coin)

                if signal_info and 'criteria' in signal_info:
                    criteria = signal_info['criteria']
                    candle_count = signal_info.get('candle_count', 0)
                    min_candles = min(min_candles, candle_count)

                    # Check if warmup active
                    validation_error = criteria.get('validation_error', '')
                    if validation_error.startswith('Warmup:'):
                        warmup_active = True

                    # Record signal check (both warmup and post-warmup)
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
                if iteration % 30 == 0:  # Every ~9 seconds
                    print(f"   🔥 Warmup: {min_candles}/{WARMUP_INTERVALS} candles")

            # Mark warmup complete
            if not warmup_active and not warmup_complete:
                warmup_complete = True
                print(f"\n✅ WARMUP COMPLETE after {min_candles} candles")
                print(f"   Now collecting signal data...\n")

            # Stop after collecting enough post-warmup checks
            post_warmup_checks = [c for c in signal_checks if not c['warmup_active']]
            if warmup_complete and len(post_warmup_checks) >= 50:
                print(f"✅ Collected {len(post_warmup_checks)} post-warmup signal checks")
                break

    except KeyboardInterrupt:
        print("\n⚠️  Audit interrupted")
    finally:
        await aggregator.stop()
        await asyncio.sleep(1)

    # Analyze signal checks
    print("\n" + "="*80)
    print("SIGNAL ANALYSIS")
    print("="*80)

    if not signal_checks:
        print("\n❌ NO SIGNALS CHECKED")
        return

    # Filter to post-warmup only
    post_warmup = [c for c in signal_checks if not c['warmup_active']]

    print(f"\n📊 Total signal checks: {len(signal_checks)}")
    print(f"📊 Post-warmup checks: {len(post_warmup)}")

    if not post_warmup:
        print("\n❌ NO POST-WARMUP SIGNALS (warmup not completed)")
        return

    # Use post-warmup checks for analysis
    signal_checks = post_warmup

    # Count by coin
    by_coin = {}
    for check in signal_checks:
        coin = check['coin']
        if coin not in by_coin:
            by_coin[coin] = {'true': 0, 'false': 0, 'validation_errors': []}

        if check['signal']:
            by_coin[coin]['true'] += 1
        else:
            by_coin[coin]['false'] += 1

        if check['validation_error']:
            by_coin[coin]['validation_errors'].append(check['validation_error'])

    print(f"\n📊 Signals by coin:")
    for coin, stats in by_coin.items():
        errors = set(stats['validation_errors'])
        error_str = f" | Errors: {', '.join(errors)}" if errors else ""
        print(f"   {coin:15s} | True: {stats['true']:3d} | False: {stats['false']:3d}{error_str}")

    # Analyze criteria for false signals
    print(f"\n📊 Criteria analysis for FALSE signals:")

    false_checks = [c for c in signal_checks if not c['signal']]
    if false_checks:
        # Take first 10 false signals
        for i, check in enumerate(false_checks[:10]):
            coin = check['coin']
            criteria = check['criteria']
            candle_count = check['candle_count']

            print(f"\n   [{i+1}] {coin} (candles: {candle_count})")

            if 'criteria_details' in criteria:
                details = criteria['criteria_details']
                for crit_name, crit_data in details.items():
                    passed = "✅" if crit_data.get('passed', False) else "❌"
                    current = crit_data.get('current', 'N/A')
                    threshold = crit_data.get('threshold', 'N/A')
                    print(f"       {passed} {crit_name:15s} | current: {current:10} | threshold: {threshold}")

    # Analyze criteria for true signals
    true_checks = [c for c in signal_checks if c['signal']]
    if true_checks:
        print(f"\n📊 Criteria analysis for TRUE signals ({len(true_checks)} found):")
        for i, check in enumerate(true_checks[:5]):
            coin = check['coin']
            criteria = check['criteria']
            candle_count = check['candle_count']

            print(f"\n   [{i+1}] {coin} (candles: {candle_count})")

            if 'criteria_details' in criteria:
                details = criteria['criteria_details']
                for crit_name, crit_data in details.items():
                    passed = "✅" if crit_data.get('passed', False) else "❌"
                    current = crit_data.get('current', 'N/A')
                    threshold = crit_data.get('threshold', 'N/A')
                    print(f"       {passed} {crit_name:15s} | current: {current:10} | threshold: {threshold}")
    else:
        print(f"\n❌ NO TRUE SIGNALS FOUND in {len(signal_checks)} checks")

    print("\n" + "="*80)

if __name__ == "__main__":
    asyncio.run(audit_signal_generation())
