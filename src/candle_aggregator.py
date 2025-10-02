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

    # DEBUG: Log if low=0 with volume
    if low_price == 0 and total_volume > 0:
        import sys
        print(f"\n{'='*80}", file=sys.stderr)
        print(f"BUG IN create_candle_from_trades!", file=sys.stderr)
        print(f"Timestamp: {timestamp}", file=sys.stderr)
        print(f"Trades count: {len(trades)}", file=sys.stderr)
        print(f"Prices: {prices}", file=sys.stderr)
        print(f"Min(prices): {min(prices)}", file=sys.stderr)
        print(f"Volumes: {volumes[:10]}..." if len(volumes) > 10 else f"Volumes: {volumes}", file=sys.stderr)
        print(f"Result: O={open_price}, H={high_price}, L={low_price}, C={close_price}, V={total_volume}", file=sys.stderr)
        print(f"{'='*80}\n", file=sys.stderr, flush=True)

    # Debug logging for volume aggregation
    # print(f"DEBUG: Created candle for timestamp {timestamp} with {len(trades)} trades, total volume: {total_volume}")
    # if volumes:
    #     print(f"DEBUG: Individual volumes: {volumes}")

    return {
        'timestamp': timestamp,
        'open': open_price,
        'high': high_price,
        'low': low_price,
        'close': close_price,
        'volume': total_volume
    }