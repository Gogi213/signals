"""
SPRINT 2: Optimized signal processing with advanced algorithms and performance improvements
- Uses vectorized calculations with numpy
- Implements exponential moving averages for better responsiveness
- Adds signal confidence scoring
- Includes adaptive timeframe selection
- Adds data validation and anomaly detection
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple, NamedTuple
from numba import jit
import warnings
warnings.filterwarnings('ignore')

class SignalResult(NamedTuple):
    """Signal result with confidence and metadata"""
    signal: bool
    confidence: float
    strength: float
    conditions: Dict[str, bool]
    metrics: Dict[str, float]

class MarketRegime(NamedTuple):
    """Market regime classification"""
    volatility: str  # 'low', 'medium', 'high'
    trend: str  # 'bull', 'bear', 'sideways'
    volume: str  # 'low', 'normal', 'high'

@jit(nopython=True)
def calculate_ema_fast(data: np.ndarray, alpha: float) -> np.ndarray:
    """Fast EMA calculation using numba"""
    result = np.zeros_like(data)
    result[0] = data[0]

    for i in range(1, len(data)):
        result[i] = alpha * data[i] + (1 - alpha) * result[i-1]

    return result

@jit(nopython=True)
def calculate_true_range_fast(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> np.ndarray:
    """Fast True Range calculation using numba"""
    n = len(highs)
    tr = np.zeros(n)

    tr[0] = highs[0] - lows[0]  # First candle

    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )

    return tr

class OptimizedSignalProcessor:
    """Advanced signal processor with optimized algorithms"""

    def __init__(self):
        self.cache = {}
        self.min_data_points = 50

    def _validate_candles(self, candles: List[Dict]) -> bool:
        """Validate candle data and detect anomalies"""
        if not candles or len(candles) < self.min_data_points:
            return False

        for i, candle in enumerate(candles):
            # Basic validation
            if not all(key in candle for key in ['open', 'high', 'low', 'close', 'volume']):
                return False

            high, low, open_price, close, volume = (
                candle['high'], candle['low'], candle['open'],
                candle['close'], candle['volume']
            )

            # Price validation
            if high < low or open_price < 0 or close < 0 or volume < 0:
                return False

            if not (low <= open_price <= high and low <= close <= high):
                return False

            # Anomaly detection - extreme price movements
            if i > 0:
                prev_close = candles[i-1]['close']
                price_change = abs(close - prev_close) / prev_close
                if price_change > 0.5:  # 50% price change - likely anomaly
                    return False

        return True

    def _extract_arrays(self, candles: List[Dict]) -> Tuple[np.ndarray, ...]:
        """Extract price arrays for vectorized calculations"""
        opens = np.array([c['open'] for c in candles], dtype=np.float64)
        highs = np.array([c['high'] for c in candles], dtype=np.float64)
        lows = np.array([c['low'] for c in candles], dtype=np.float64)
        closes = np.array([c['close'] for c in candles], dtype=np.float64)
        volumes = np.array([c['volume'] for c in candles], dtype=np.float64)

        return opens, highs, lows, closes, volumes

    def calculate_optimized_atr(self, candles: List[Dict], period: int = 14, use_ema: bool = True) -> np.ndarray:
        """Optimized ATR calculation with EMA option"""
        cache_key = f"atr_{len(candles)}_{period}_{use_ema}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        _, highs, lows, closes, _ = self._extract_arrays(candles)

        # Fast true range calculation
        tr = calculate_true_range_fast(highs, lows, closes)

        if use_ema:
            # Use EMA for more responsive ATR
            alpha = 2.0 / (period + 1)
            atr = calculate_ema_fast(tr, alpha)
        else:
            # Traditional SMA
            atr = pd.Series(tr).rolling(window=period, min_periods=1).mean().values

        self.cache[cache_key] = atr
        return atr

    def calculate_optimized_natr(self, candles: List[Dict], period: int = 20) -> np.ndarray:
        """Optimized NATR calculation"""
        cache_key = f"natr_{len(candles)}_{period}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        _, _, _, closes, _ = self._extract_arrays(candles)
        atr = self.calculate_optimized_atr(candles, period)

        # Vectorized NATR calculation
        natr = (atr / closes) * 100
        natr = np.nan_to_num(natr, 0.0)  # Handle division by zero

        self.cache[cache_key] = natr
        return natr

    def calculate_adaptive_percentiles(self, data: np.ndarray, period: int, percentile: float) -> np.ndarray:
        """Calculate rolling percentiles with adaptive period"""
        result = np.zeros_like(data)

        for i in range(len(data)):
            # Adaptive window size - smaller for recent data
            adaptive_period = min(period, i + 1)
            start_idx = max(0, i - adaptive_period + 1)
            window = data[start_idx:i + 1]
            result[i] = np.percentile(window, percentile)

        return result

    def detect_market_regime(self, candles: List[Dict]) -> MarketRegime:
        """Detect current market regime for adaptive parameters"""
        if len(candles) < 20:
            return MarketRegime('medium', 'sideways', 'normal')

        _, _, _, closes, volumes = self._extract_arrays(candles[-20:])

        # Volatility analysis
        returns = np.diff(closes) / closes[:-1]
        volatility = np.std(returns) * 100

        if volatility < 1.0:
            vol_regime = 'low'
        elif volatility > 3.0:
            vol_regime = 'high'
        else:
            vol_regime = 'medium'

        # Trend analysis (linear regression slope)
        x = np.arange(len(closes))
        slope = np.polyfit(x, closes, 1)[0]
        slope_pct = (slope / closes[0]) * 100

        if slope_pct > 0.5:
            trend_regime = 'bull'
        elif slope_pct < -0.5:
            trend_regime = 'bear'
        else:
            trend_regime = 'sideways'

        # Volume analysis
        volume_ma = np.mean(volumes)
        recent_volume = np.mean(volumes[-5:])

        if recent_volume < volume_ma * 0.7:
            vol_level = 'low'
        elif recent_volume > volume_ma * 1.3:
            vol_level = 'high'
        else:
            vol_level = 'normal'

        return MarketRegime(vol_regime, trend_regime, vol_level)

    def check_enhanced_volume_condition(self, candles: List[Dict], regime: MarketRegime) -> Tuple[bool, float]:
        """Enhanced volume condition with regime adaptation"""
        _, _, _, _, volumes = self._extract_arrays(candles)

        # Adaptive parameters based on market regime
        if regime.volatility == 'high':
            vol_period, vol_pctl = 15, 10.0  # More relaxed in high volatility
        elif regime.volatility == 'low':
            vol_period, vol_pctl = 30, 3.0   # More strict in low volatility
        else:
            vol_period, vol_pctl = 20, 5.0   # Default

        percentiles = self.calculate_adaptive_percentiles(volumes, vol_period, vol_pctl)

        current_volume = volumes[-1]
        current_percentile = percentiles[-1]

        condition = current_volume <= current_percentile
        strength = max(0, (current_percentile - current_volume) / current_percentile) if current_percentile > 0 else 0

        return condition, strength

    def check_enhanced_range_condition(self, candles: List[Dict], regime: MarketRegime) -> Tuple[bool, float]:
        """Enhanced range condition with volatility adaptation"""
        _, highs, lows, _, _ = self._extract_arrays(candles)
        ranges = highs - lows

        # Adaptive parameters
        if regime.volatility == 'high':
            range_period, rng_pctl = 20, 15.0
        elif regime.volatility == 'low':
            range_period, rng_pctl = 40, 3.0
        else:
            range_period, rng_pctl = 30, 5.0

        percentiles = self.calculate_adaptive_percentiles(ranges, range_period, rng_pctl)

        current_range = ranges[-1]
        current_percentile = percentiles[-1]

        condition = current_range <= current_percentile
        strength = max(0, (current_percentile - current_range) / current_percentile) if current_percentile > 0 else 0

        return condition, strength

    def check_enhanced_natr_condition(self, candles: List[Dict], regime: MarketRegime) -> Tuple[bool, float]:
        """Enhanced NATR condition with market adaptation"""
        natr_values = self.calculate_optimized_natr(candles, period=20)

        # Adaptive NATR threshold based on regime
        if regime.volatility == 'high':
            natr_min = 1.2
        elif regime.volatility == 'low':
            natr_min = 0.3
        else:
            natr_min = 0.6

        current_natr = natr_values[-1]
        condition = current_natr > natr_min
        strength = min(1.0, current_natr / natr_min) if natr_min > 0 else 0

        return condition, strength

    def check_momentum_filter(self, candles: List[Dict], regime: MarketRegime) -> Tuple[bool, float]:
        """Advanced momentum filter with multiple timeframes"""
        _, _, _, closes, _ = self._extract_arrays(candles)

        # Multiple momentum checks
        lookbacks = [10, 20, 50]
        momentum_scores = []

        for lookback in lookbacks:
            if len(closes) >= lookback + 1:
                current_close = closes[-1]
                lookback_close = closes[-lookback-1]

                if lookback_close != 0:
                    momentum = (current_close - lookback_close) / abs(lookback_close)
                    momentum_scores.append(momentum)

        if not momentum_scores:
            return True, 0.5

        avg_momentum = np.mean(momentum_scores)

        # Adaptive threshold based on market trend
        if regime.trend == 'bull':
            min_momentum = -0.02  # More relaxed in bull market
        elif regime.trend == 'bear':
            min_momentum = 0.01   # More strict in bear market
        else:
            min_momentum = -0.001  # Default for sideways

        condition = avg_momentum >= min_momentum
        strength = max(0, min(1, (avg_momentum - min_momentum) / 0.05 + 0.5))

        return condition, strength

    def calculate_signal_confidence(self, conditions: Dict[str, bool], strengths: Dict[str, float]) -> float:
        """Calculate overall signal confidence based on condition strengths"""
        if not all(conditions.values()):
            return 0.0

        # Weighted confidence calculation
        weights = {
            'volume': 0.25,
            'range': 0.30,
            'natr': 0.25,
            'momentum': 0.20
        }

        confidence = sum(weights.get(key, 0.25) * strength for key, strength in strengths.items())
        return min(1.0, confidence)

    def generate_optimized_signal(self, candles: List[Dict]) -> SignalResult:
        """Generate signal with advanced algorithms and confidence scoring"""

        # Validate input data
        if not self._validate_candles(candles):
            return SignalResult(False, 0.0, 0.0, {}, {})

        # Detect market regime
        regime = self.detect_market_regime(candles)

        # Check all conditions with strengths
        volume_condition, volume_strength = self.check_enhanced_volume_condition(candles, regime)
        range_condition, range_strength = self.check_enhanced_range_condition(candles, regime)
        natr_condition, natr_strength = self.check_enhanced_natr_condition(candles, regime)
        momentum_condition, momentum_strength = self.check_momentum_filter(candles, regime)

        conditions = {
            'volume': volume_condition,
            'range': range_condition,
            'natr': natr_condition,
            'momentum': momentum_condition
        }

        strengths = {
            'volume': volume_strength,
            'range': range_strength,
            'natr': natr_strength,
            'momentum': momentum_strength
        }

        # Generate final signal
        signal = all(conditions.values())
        confidence = self.calculate_signal_confidence(conditions, strengths)
        overall_strength = np.mean(list(strengths.values()))

        # Additional metrics
        metrics = {
            'regime_volatility': regime.volatility,
            'regime_trend': regime.trend,
            'regime_volume': regime.volume,
            'candle_count': len(candles),
            'data_quality': 1.0 if len(candles) >= self.min_data_points else len(candles) / self.min_data_points
        }

        return SignalResult(signal, confidence, overall_strength, conditions, metrics)

def process_trades_for_optimized_signals(trades: List[Dict], timeframe_ms: int = 10000) -> Tuple[bool, Dict]:
    """Process trades with optimized signal generation"""
    from .candle_aggregator import aggregate_trades_to_candles

    # Aggregate trades to candles
    candles = aggregate_trades_to_candles(trades, timeframe_ms)

    # Generate optimized signal
    processor = OptimizedSignalProcessor()
    result = processor.generate_optimized_signal(candles)

    # Prepare response data
    signal_data = {
        'signal': result.signal,
        'confidence': result.confidence,
        'strength': result.strength,
        'conditions': result.conditions,
        'metrics': result.metrics,
        'candle_count': len(candles),
        'last_candle': candles[-1] if candles else None
    }

    return result.signal, signal_data