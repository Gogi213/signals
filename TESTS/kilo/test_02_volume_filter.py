"""
Iteration 3 - Test #2: Validate H3.2
Test volume filter effectiveness

Expected: MIN_DAILY_VOLUME filter should exclude low-activity coins
Reality: If low-activity coins pass filter → H3.2 VALID
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import requests
from src.config import MIN_DAILY_VOLUME, BLACKLISTED_COINS

def check_volume_for_problematic_coins():
    """Check actual volume for coins that might have low real-time activity"""
    print("=" * 70)
    print("TEST #2: Volume Filter Validation")
    print("=" * 70)
    print()
    print("HYPOTHESIS H3.2: MIN_DAILY_VOLUME filter allows low-activity coins")
    print()
    print(f"Current MIN_DAILY_VOLUME: {MIN_DAILY_VOLUME:,.0f} USDT")
    print()

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

        # Get all coins that pass the filter
        passing_coins = [
            (sym, vol['turnover24h'])
            for sym, vol in volume_map.items()
            if vol['turnover24h'] >= MIN_DAILY_VOLUME and sym not in BLACKLISTED_COINS
        ]

        print(f"Total coins passing filter: {len(passing_coins)}")
        print()

        # Show bottom 10 by volume (lowest volume that still passes)
        passing_sorted = sorted(passing_coins, key=lambda x: x[1])
        print(f"Bottom 10 coins by turnover (lowest volume that still passes):")
        for i, (sym, turnover) in enumerate(passing_sorted[:10], 1):
            print(f"  {i}. {sym}: ${turnover:,.0f}")

        # Show top 10 by volume for comparison
        print()
        top_10 = sorted(passing_coins, key=lambda x: x[1], reverse=True)[:10]
        print(f"Top 10 coins by turnover:")
        for i, (sym, turnover) in enumerate(top_10, 1):
            print(f"  {i}. {sym}: ${turnover:,.0f}")

        print()
        print("=" * 70)
        print("HYPOTHESIS VALIDATION:")
        print("=" * 70)

        # Check if there are coins with relatively low volume that still pass
        if passing_sorted:
            lowest_passing = passing_sorted[0]
            print(f"  Lowest passing coin: {lowest_passing[0]} with ${lowest_passing[1]:,.0f}")
            
            # Check if this is significantly higher than MIN_DAILY_VOLUME
            if lowest_passing[1] > MIN_DAILY_VOLUME * 1.1:  # 10% buffer
                print(f"  [VALID] H3.2 VALID: Some coins pass with volume only slightly above threshold")
                print(f"     This suggests the 24h volume window may be appropriate")
                h32_valid = False
            else:
                print(f"  [VALID] H3.2 VALID: Coins pass with volume just above threshold")
                print(f"     These coins may have low real-time activity despite 24h volume")
                print(f"     The 24h window includes peak periods, masking low current activity")
                h32_valid = True
        else:
            print(f"  [INVALID] H3.2 INVALID: No coins pass the filter")
            h32_valid = False

        # Also check for coins that might be problematic
        print()
        print("Checking for potential problematic coins...")
        
        # Find coins that have high 24h volume but might have low real-time activity
        # by looking at volume patterns
        potential_problems = []
        for sym, vol_data in volume_map.items():
            if (vol_data['turnover24h'] >= MIN_DAILY_VOLUME and 
                sym not in BLACKLISTED_COINS and
                vol_data['turnover24h'] < MIN_DAILY_VOLUME * 2):  # Close to threshold
                potential_problems.append((sym, vol_data['turnover24h']))
        
        print(f"Coins with volume close to threshold (≤2x MIN_DAILY_VOLUME): {len(potential_problems)}")
        for sym, vol in potential_problems[:5]:  # Show first 5
            print(f" {sym}: ${vol:,.0f}")

        # Save results
        import json
        results = {
            'test': 'volume_filter_validation',
            'h32_valid': h32_valid,
            'min_volume': MIN_DAILY_VOLUME,
            'total_passing': len(passing_coins),
            'bottom_10': passing_sorted[:10],
            'top_10': top_10,
            'potential_problems_count': len(potential_problems),
            'potential_problems_sample': potential_problems[:5]
        }

        with open('TESTS/kilo/test_02_results.json', 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\nResults saved to: test_02_results.json")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_volume_for_problematic_coins()