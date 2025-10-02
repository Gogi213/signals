"""
Module for aggregating trades into candles
"""
from typing import List, Dict


def create_candle_from_trades(trades: List[Dict], timestamp: int) -> Dict:
    """
    Create a candle from a list of trades
    """
    if not trades:
        return {
            'timestamp': timestamp,
            'open': 0,
            'high': 0,
            'low': 0,
            'close': 0,
            'volume': 0
        }
    
    prices = [trade['price'] for trade in trades]
    volumes = [trade['size'] for trade in trades]

    open_price = trades[0]['price']
    close_price = trades[-1]['price']
    high_price = max(prices)
    low_price = min(prices)
    total_volume = sum(volumes)


    return {
        'timestamp': timestamp,
        'open': open_price,
        'high': high_price,
        'low': low_price,
        'close': close_price,
        'volume': total_volume
    }