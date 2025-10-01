"""
Check if blacklisted symbols exist on Binance Futures
"""
import sys
sys.path.insert(0, '../..')

from src.trading_api import get_futures_symbols
from src.config import BLACKLISTED_COINS

symbols = get_futures_symbols()

print("Checking BLACKLISTED_COINS on Binance Futures:\n")

for coin in BLACKLISTED_COINS:
    exists = coin in symbols
    status = "EXISTS" if exists else "NOT FOUND"
    print(f"  {coin:15} -> {status}")

print(f"\nTotal Binance symbols: {len(symbols)}")
