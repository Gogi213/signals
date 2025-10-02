"""
Module for processing trading signals based on specified conditions
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple


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
    Uses Typical Price (high + low + close) / 3 as denominator (matches backtester)
    """
    atr_values = calculate_atr(candles, period)
    natr_values = []

    for i, candle in enumerate(candles):
        # Typical Price = (high + low + close) / 3
        typical_price = (candle['high'] + candle['low'] + candle['close']) / 3.0
        if typical_price and typical_price != 0:
            natr = (atr_values[i] / typical_price) * 100
        else:
            natr = 0.0
        natr_values.append(natr)

    return natr_values


def calculate_mma_wilder(prices: List[float], period: int) -> List[float]:
    """
    Calculate Moving Average using Wilder's method (MMA)
    Wilder's method uses exponential smoothing with alpha = 1/period
    """
    if not prices:
        return []
    
    mma_values = []
    
    # Initialize with first price
    if prices:
        mma_values.append(prices[0])
    
    # Calculate subsequent values using Wilder's smoothing
    alpha = 1.0 / period
    for i in range(1, len(prices)):
        mma_value = alpha * prices[i] + (1 - alpha) * mma_values[i-1]
        mma_values.append(mma_value)
    
    return mma_values


def calculate_mma_wilder_from_candles(candles: List[Dict], period: int, price_type: str = 'close') -> List[float]:
    """
    Calculate Moving Average using Wilder's method from candle data
    price_type: 'close', 'high', 'low', 'open', 'typical' (h+l+c)/3
    """
    if not candles:
        return []
    
    # Extract prices based on type
    if price_type == 'close':
        prices = [candle['close'] for candle in candles]
    elif price_type == 'high':
        prices = [candle['high'] for candle in candles]
    elif price_type == 'low':
        prices = [candle['low'] for candle in candles]
    elif price_type == 'open':
        prices = [candle['open'] for candle in candles]
    elif price_type == 'typical':
        prices = [(candle['high'] + candle['low'] + candle['close']) / 3.0 for candle in candles]
    else:
        # Default to close
        prices = [candle['close'] for candle in candles]
    
    return calculate_mma_wilder(prices, period)


def calculate_mma_wilder_true_range(candles: List[Dict], period: int = 20) -> List[float]:
    """
    Calculate Moving Average using Wilder's method for True Range
    This replaces NATR (Normalized Average True Range)
    """
    if len(candles) < 2:
        return [0.0] * len(candles)
    
    # Calculate True Range values
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
    
    # Pad with zero for the first value
    true_ranges = [0.0] + true_ranges
    
    # Calculate MMA using Wilder's method
    return calculate_mma_wilder(true_ranges, period)


def calculate_mma_wilder_normalized(candles: List[Dict], period: int = 20) -> List[float]:
    """
    Calculate Moving Average using Wilder's method for Normalized True Range
    This replaces NATR (Normalized Average True Range)
    """
    if len(candles) < 2:
        return [0.0] * len(candles)
    
    # Calculate MMA of True Range
    mma_tr = calculate_mma_wilder_true_range(candles, period)
    
    # Normalize by Typical Price
    mma_normalized = []
    for i, candle in enumerate(candles):
        # Typical Price = (high + low + close) / 3
        typical_price = (candle['high'] + candle['low'] + candle['close']) / 3.0
        if typical_price and typical_price != 0:
            normalized = (mma_tr[i] / typical_price) * 100
        else:
            normalized = 0.0
        mma_normalized.append(normalized)
    
    return mma_normalized


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
                             vol_pctl: float = 5.0) -> Tuple[bool, Dict]:
    """
    Check if volume is low (lowVol condition)
    Returns (passed, details)
    """
    if not candles:
        return False, {'current': 0, 'threshold': 0, 'passed': False}

    volumes = [candle['volume'] for candle in candles]
    percentiles = calculate_percentile(volumes, vol_period, vol_pctl)

    # Check the last candle
    current_volume = volumes[-1]
    current_percentile = percentiles[-1]
    passed = current_volume <= current_percentile

    return passed, {
        'current': round(current_volume, 2),
        'threshold': round(current_percentile, 2),
        'passed': passed
    }


def check_narrow_range_condition(candles: List[Dict],
                               range_period: int = 30,
                               rng_pctl: float = 5.0) -> Tuple[bool, Dict]:
    """
    Check if price range is narrow (narrowRng condition)
    Returns (passed, details)
    """
    if not candles:
        return False, {'current': 0, 'threshold': 0, 'passed': False}

    ranges = [(candle['high'] - candle['low']) for candle in candles]
    percentiles = calculate_percentile(ranges, range_period, rng_pctl)

    # Check the last candle
    current_range = ranges[-1]
    current_percentile = percentiles[-1]
    passed = current_range <= current_percentile

    return passed, {
        'current': round(current_range, 6),
        'threshold': round(current_percentile, 6),
        'passed': passed
    }


def check_high_natr_condition(candles: List[Dict],
                            natr_period: int = 20,
                            natr_min: float = 0.6) -> Tuple[bool, Dict]:
    """
    Check if NATR is high (highNatr condition)
    DEPRECATED: Use check_high_mma_condition instead
    Returns (passed, details)
    """
    if not candles:
        return False, {'current': 0, 'threshold': natr_min, 'passed': False}

    natr_values = calculate_natr(candles, natr_period)

    # Check the last candle
    current_natr = natr_values[-1]
    passed = current_natr > natr_min

    return passed, {
        'current': round(current_natr, 3),
        'threshold': natr_min,
        'passed': passed
    }


def check_high_mma_condition(candles: List[Dict],
                           mma_period: int = 20,
                           mma_min: float = 0.6) -> Tuple[bool, Dict]:
    """
    Check if MMA (Wilder) Normalized True Range is high (replaces highNatr condition)
    Returns (passed, details)
    """
    if not candles:
        return False, {'current': 0, 'threshold': mma_min, 'passed': False}

    mma_values = calculate_mma_wilder_normalized(candles, mma_period)

    # Check the last candle
    current_mma = mma_values[-1]
    passed = current_mma > mma_min

    return passed, {
        'current': round(current_mma, 3),
        'threshold': mma_min,
        'passed': passed
    }


def check_growth_filter(candles: List[Dict],
                       lookback_period: int = 50,
                       min_growth_pct: float = -0.1) -> Tuple[bool, Dict]:
    """
    Check growth filter condition
    Matches backtester formula: (close - price_n_bars_ago) / price_n_bars_ago * 100
    Returns (passed, details)
    """
    if len(candles) < lookback_period + 1:
        return True, {'current': 0, 'threshold': min_growth_pct, 'passed': True, 'note': 'insufficient_data'}

    current_close = candles[-1]['close']
    lookback_close = candles[-lookback_period - 1]['close']

    if lookback_close and lookback_close != 0:
        # Matches backtester: no abs() in denominator
        growth_pct = ((current_close - lookback_close) / lookback_close) * 100
        passed = growth_pct >= min_growth_pct
        return passed, {
            'current': round(growth_pct, 2),
            'threshold': min_growth_pct,
            'passed': passed
        }
    else:
        return True, {'current': 0, 'threshold': min_growth_pct, 'passed': True, 'note': 'zero_lookback'}


def generate_signal(candles: List[Dict]) -> Tuple[bool, Dict]:
    """
    Generate signal based on all conditions
    Returns (signal, detailed_info) with actual values and pass/fail status
    """
    detailed_info = {
        'validation_error': '',
        'candle_count': len(candles),
        'criteria_details': {}
    }

    if len(candles) < 20:  # Need enough data for all checks
        detailed_info['validation_error'] = f'Insufficient data: {len(candles)} candles (need 20+)'
        return False, detailed_info

    # Check if last candle has zero volume (forward-fill) - no signal for inactive markets
    if candles[-1]['volume'] == 0:
        detailed_info['validation_error'] = 'No trades in last candle (forward-fill)'
        return False, detailed_info

    # Validate candle data to prevent negative ranges
    for i, candle in enumerate(candles):
        if candle['high'] < candle['low']:
            detailed_info['validation_error'] = f'Invalid candle {i}: high < low'
            return False, detailed_info
        if candle['close'] < candle['low'] or candle['close'] > candle['high']:
            detailed_info['validation_error'] = f'Invalid candle {i}: close out of range'
            return False, detailed_info

    # Check all conditions with detailed values
    low_vol_passed, low_vol_details = check_low_volume_condition(candles)
    narrow_rng_passed, narrow_rng_details = check_narrow_range_condition(candles)
    high_mma_passed, high_mma_details = check_high_mma_condition(candles)
    growth_filter_passed, growth_filter_details = check_growth_filter(candles)

    # Store detailed criteria
    detailed_info['criteria_details'] = {
        'low_vol': low_vol_details,
        'narrow_rng': narrow_rng_details,
        'high_mma': high_mma_details,
        'growth_filter': growth_filter_details
    }

    # Store simple pass/fail for backward compatibility
    detailed_info['low_vol'] = low_vol_passed
    detailed_info['narrow_rng'] = narrow_rng_passed
    detailed_info['high_mma'] = high_mma_passed
    detailed_info['high_natr'] = high_mma_passed  # Keep for backward compatibility
    detailed_info['growth_filter'] = growth_filter_passed

    # Combine all conditions
    signal_raw = low_vol_passed and narrow_rng_passed and high_mma_passed
    final_signal = signal_raw and growth_filter_passed

    return final_signal, detailed_info


