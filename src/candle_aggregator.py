"""
Module for aggregating trades into candles and calculating metrics
"""
import pandas as pd
from typing import List, Dict, Optional


def aggregate_trades_to_candles(trades: List[Dict], timeframe_ms: int = 1000) -> List[Dict]:
    """
    Aggregate trades into candles based on timeframe
    Default is 1-second candles (1000 ms) - general purpose function
    For signals, typically used with 10-second timeframe (10000 ms)
    """
    if not trades:
        return []


    # Round timestamp to the specified timeframe
    for trade in trades:
        trade['rounded_time'] = (trade['timestamp'] // timeframe_ms) * timeframe_ms
    
    # Sort trades by time
    trades.sort(key=lambda x: x['rounded_time'])
    
    # Group trades by time intervals
    candles = []
    if not trades:
        return candles
        
    current_time = trades[0]['rounded_time']
    current_trades = []
    
    for trade in trades:
        if trade['rounded_time'] == current_time:
            current_trades.append(trade)
        else:
            # Create candle from accumulated trades
            if current_trades:
                candle = create_candle_from_trades(current_trades, current_time)
                candles.append(candle)
            
            # Move to next interval
            current_time = trade['rounded_time']
            current_trades = [trade]
    
    # Process last interval
    if current_trades:
        candle = create_candle_from_trades(current_trades, current_time)
        candles.append(candle)
    
    return candles


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
    
    # Ensure high >= low and other validations
    if low_price > high_price:
        # Swap if needed
        high_price, low_price = low_price, high_price
    
    if open_price < low_price:
        open_price = low_price
    elif open_price > high_price:
        open_price = high_price
        
    if close_price < low_price:
        close_price = low_price
    elif close_price > high_price:
        close_price = high_price
    
    return {
        'timestamp': timestamp,
        'open': open_price,
        'high': high_price,
        'low': low_price,
        'close': close_price,
        'volume': total_volume
    }


def calculate_avg_candle_size_percentage(candles: List[Dict]) -> float:
    """
    Calculate average candle size in percentage
    """
    if not candles:
        return 0
    
    df = pd.DataFrame(candles)
    df['Candle_Size'] = (df['high'] - df['low']) / df['low'] * 100  # Candle size in percentage
    
    return df['Candle_Size'].mean()


def calculate_scaled_avg_candle_size(candles: List[Dict]) -> int:
    """
    Calculate average candle size and scale it (multiply by 100 and round to integer)
    """
    avg_size = calculate_avg_candle_size_percentage(candles)
    return round(avg_size * 1000)