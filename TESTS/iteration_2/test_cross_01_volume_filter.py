"""
Cross-Audit #1 - Test C2.1: Volume Filter Validation

Check if low-activity coins should have passed MIN_DAILY_VOLUME filter
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import requests
from src.config import MIN_DAILY_VOLUME, BLACKLISTED_COINS

def check_volume_for_problem_coins():
    """Check actual volume for coins with high zero-volume %"""
    print("=" * 70)
    print("CROSS-AUDIT TEST C2.1: Volume Filter Validation")
    print("=" * 70)
    print()
    print("HYPOTHESIS C2.1: MIN_DAILY_VOLUME filter allows low-activity coins")
    print()
    print(f"Current MIN_DAILY_VOLUME: {MIN_DAILY_VOLUME:,.0f} USDT")
    print()

    # Problem coins from Test #2
    problem_coins = ['FARTCOINUSDT', 'FFUSDT', 'DRIFTUSDT']

    # Fetch tickers
    url = "https://api.bybit.com/v5/market/tickers"
    params = {'category': 'linear'}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data['retCode'] != 0:
            print(f"API Error: {data['retMsg']}")
            return

        # Build volume map
        volume_map = {}
        for item in data['result']['list']:
            symbol = item['symbol']
            turnover24h = float(item.get('turnover24h', 0))
            volume24h = float(item.get('volume24h', 0))  # Coin volume
            lastPrice = float(item.get('lastPrice', 0))

            volume_map[symbol] = {
                'turnover24h': turnover24h,  # USDT volume
                'volume24h': volume24h,       # Coin volume
                'lastPrice': lastPrice
            }

        # Check problem coins
        print(f"Analyzing problem coins (high zero-volume %):")
        print()

        for coin in problem_coins:
            if coin in volume_map:
                data = volume_map[coin]
                turnover = data['turnover24h']
                volume = data['volume24h']
                price = data['lastPrice']

                passes_filter = turnover >= MIN_DAILY_VOLUME
                status = "[PASS]" if passes_filter else "[FAIL]"

                print(f"{coin}:")
                print(f"  Turnover (24h): ${turnover:,.0f} USDT")
                print(f"  Volume (24h): {volume:,.0f} coins")
                print(f"  Last Price: ${price:.4f}")
                print(f"  Filter status: {status} (min: ${MIN_DAILY_VOLUME:,.0f})")
                print()

        # Check all filtered coins
        filtered = [
            (sym, vol['turnover24h'])
            for sym, vol in volume_map.items()
            if vol['turnover24h'] >= MIN_DAILY_VOLUME and sym not in BLACKLISTED_COINS
        ]

        print(f"Total coins passing filter: {len(filtered)}")
        print()

        # Show bottom 10 by volume
        filtered_sorted = sorted(filtered, key=lambda x: x[1])
        print(f"Bottom 10 coins by turnover (lowest volume that still passes):")
        for i, (sym, turnover) in enumerate(filtered_sorted[:10], 1):
            print(f"  {i}. {sym}: ${turnover:,.0f}")

        print()
        print("=" * 70)
        print("HYPOTHESIS VALIDATION:")
        print("=" * 70)

        # Check if problem coins passed
        problem_passing = sum(1 for c in problem_coins if c in volume_map and volume_map[c]['turnover24h'] >= MIN_DAILY_VOLUME)

        if problem_passing > 0:
            print(f"  [VALID] C2.1 VALID: Problem coins ARE passing filter")
            print(f"     {problem_passing}/{len(problem_coins)} problem coins pass MIN_DAILY_VOLUME")
            print(f"     They have low real-time activity but high 24h turnover")
            print(f"     Possible reasons:")
            print(f"       - Turnover calculated over full 24h (includes peaks)")
            print(f"       - Current time is low-activity period")
            print(f"       - Filter should use shorter window (e.g. 1h, 4h)")
            c21_valid = True
        else:
            print(f"  [INVALID] C2.1 INVALID: Problem coins NOT passing filter")
            print(f"     They should have been excluded")
            c21_valid = False

        # Save results
        import json
        results = {
            'test': 'volume_filter_validation',
            'c21_valid': c21_valid,
            'min_volume': MIN_DAILY_VOLUME,
            'problem_coins': {
                coin: {
                    'turnover': volume_map[coin]['turnover24h'],
                    'passes': volume_map[coin]['turnover24h'] >= MIN_DAILY_VOLUME
                }
                for coin in problem_coins if coin in volume_map
            },
            'total_passing': len(filtered),
            'bottom_10': filtered_sorted[:10]
        }

        with open('TESTS/iteration_2/test_cross_01_results.json', 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\nResults saved to: test_cross_01_results.json")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_volume_for_problem_coins()
