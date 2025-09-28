"""
Module for processing trading signals based on specified conditions
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from .candle_aggregator import aggregate_trades_to_candles


def calculate_atr(candles: List[Dict], period: int = 14) -> List[float]:
    """
    Calculate Average True Range (ATR) for the given candles
    """
    if len(candles) < 2:
        return [0.0] * len(candles)
    
    true_ranges = []
    for i in range(1, len(candles)):
        high = candles[i]['high']
        low = candles[i]['low']
        prev_close = candles[i-1]['close']
        
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        true_ranges.append(tr)
    
    # Pad with zeros for the first value
    true_ranges = [0.0] + true_ranges
    
    # Calculate ATR using simple moving average
    atr_values = []
    for i in range(len(true_ranges)):
        if i < period:
            # Use available data for initial values
            start_idx = max(0, i - period + 1)
            atr = sum(true_ranges[start_idx:i+1]) / (i - start_idx + 1) if i >= start_idx else 0.0
        else:
            atr = sum(true_ranges[i - period + 1:i + 1]) / period
        
        atr_values.append(atr)
    
    return atr_values


def calculate_natr(candles: List[Dict], period: int = 20) -> List[float]:
    """
    Calculate Normalized Average True Range (NATR)
    """
    atr_values = calculate_atr(candles, period)
    natr_values = []
    
    for i, candle in enumerate(candles):
        close_price = candle['close']
        if close_price and close_price != 0:
            natr = (atr_values[i] / close_price) * 100
        else:
            natr = 0.0
        natr_values.append(natr)
    
    return natr_values


def calculate_percentile(data: List[float], period: int, percentile: float) -> List[float]:
    """
    Calculate rolling percentile for the given data
    """
    if not data:
        return []
    
    result = []
    for i in range(len(data)):
        start_idx = max(0, i - period + 1)
        window = data[start_idx:i + 1]
        result.append(np.percentile(window, percentile))
    
    return result


def check_low_volume_condition(candles: List[Dict], 
                             vol_period: int = 20, 
                             vol_pctl: float = 5.0) -> bool:
    """
    Check if volume is low (lowVol condition)
    """
    if not candles:
        return False
    
    volumes = [candle['volume'] for candle in candles]
    percentiles = calculate_percentile(volumes, vol_period, vol_pctl)
    
    # Check the last candle
    current_volume = volumes[-1]
    current_percentile = percentiles[-1]
    
    return current_volume <= current_percentile


def check_narrow_range_condition(candles: List[Dict], 
                               range_period: int = 30, 
                               rng_pctl: float = 5.0) -> bool:
    """
    Check if price range is narrow (narrowRng condition)
    """
    if not candles:
        return False
    
    ranges = [(candle['high'] - candle['low']) for candle in candles]
    percentiles = calculate_percentile(ranges, range_period, rng_pctl)
    
    # Check the last candle
    current_range = ranges[-1]
    current_percentile = percentiles[-1]
    
    return current_range <= current_percentile


def check_high_natr_condition(candles: List[Dict], 
                            natr_period: int = 20, 
                            natr_min: float = 0.6) -> bool:
    """
    Check if NATR is high (highNatr condition)
    """
    if not candles:
        return False
    
    natr_values = calculate_natr(candles, natr_period)
    
    # Check the last candle
    current_natr = natr_values[-1]
    
    return current_natr > natr_min


def check_growth_filter(candles: List[Dict], 
                       lookback_period: int = 50, 
                       min_growth_pct: float = -0.1) -> bool:
    """
    Check growth filter condition
    """
    if len(candles) < lookback_period + 1:
        return True  # If not enough data, consider condition satisfied
    
    current_close = candles[-1]['close']
    lookback_close = candles[-lookback_period - 1]['close']
    
    if lookback_close and lookback_close != 0:
        growth_pct = ((current_close - lookback_close) / abs(lookback_close)) * 100
        return growth_pct >= min_growth_pct
    else:
        return True  # If lookback close is zero, consider condition satisfied


def generate_signal(candles: List[Dict]) -> bool:
    """
    Generate signal based on all conditions
    Returns True if all conditions are met, False otherwise
    """
    if len(candles) < 20:  # Need enough data for all checks
        return False
    
    # Validate candle data to prevent negative ranges
    for i, candle in enumerate(candles):
        if candle['high'] < candle['low']:
            print(f"Warning: Invalid candle {i}: high ({candle['high']}) < low ({candle['low']})")
            return False
        if candle['close'] < candle['low'] or candle['close'] > candle['high']:
            print(f"Warning: Invalid candle {i}: close ({candle['close']}) not in range [{candle['low']}, {candle['high']}]")
            return False
    
    # Check all conditions
    low_vol = check_low_volume_condition(candles)
    narrow_rng = check_narrow_range_condition(candles)
    high_natr = check_high_natr_condition(candles)
    growth_filter = check_growth_filter(candles)
    
    # Combine all conditions
    signal_raw = low_vol and narrow_rng and high_natr
    final_signal = signal_raw and growth_filter
    
    return final_signal


def process_trades_for_signals(trades: List[Dict], 
                              timeframe_ms: int = 10000) -> Tuple[bool, Dict]:
    """
    Process trades and generate signals based on conditions
    """
    # Aggregate trades to candles
    candles = aggregate_trades_to_candles(trades, timeframe_ms)
    
    # Generate signal
    signal = generate_signal(candles)
    
    # Prepare signal data
    signal_data = {
        'signal': signal,
        'candle_count': len(candles),
        'last_candle': candles[-1] if candles else None
    }
    
    return signal, signal_data