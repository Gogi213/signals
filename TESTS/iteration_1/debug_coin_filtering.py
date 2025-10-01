"""Quick debug - why only one coin?"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.trading_api import get_all_symbols_by_volume
from src.config import MIN_DAILY_VOLUME, BLACKLISTED_COINS

print(f"MIN_DAILY_VOLUME: {MIN_DAILY_VOLUME:,}")
print(f"BLACKLISTED_COINS: {BLACKLISTED_COINS}")

coins = get_all_symbols_by_volume()
print(f"\nTotal coins filtered: {len(coins)}")
print(f"Coins: {coins}")