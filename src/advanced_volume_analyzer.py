"""
SPRINT 2: Advanced volume and volatility analysis
- Multi-dimensional volume analysis (price-volume, time-volume)
- Volume profile and VWAP calculations
- Volatility clustering detection
- Order flow analysis simulation
- Volume-based support/resistance detection
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, NamedTuple, Optional
from scipy import stats
from scipy.signal import find_peaks
import warnings
warnings.filterwarnings('ignore')

class VolumeProfile(NamedTuple):
    """Volume profile data structure"""
    levels: np.ndarray  # Price levels
    volumes: np.ndarray  # Volume at each level
    poc: float  # Point of Control (highest volume)
    value_area_high: float
    value_area_low: float
    value_area_volume_pct: float

class VolumeAnalysis(NamedTuple):
    """Comprehensive volume analysis result"""
    relative_volume: float
    volume_trend: str  # 'increasing', 'decreasing', 'stable'
    volume_distribution: str  # 'normal', 'skewed_high', 'skewed_low'
    accumulation_distribution: float
    volume_weighted_price: float
    volume_strength: float  # 0-1 scale

class VolatilityAnalysis(NamedTuple):
    """Volatility analysis result"""
    realized_volatility: float
    volatility_regime: str  # 'low', 'normal', 'high', 'extreme'
    volatility_clustering: bool
    garman_klass_volatility: float
    yang_zhang_volatility: float
    volatility_trend: str  # 'increasing', 'decreasing', 'stable'

class AdvancedVolumeAnalyzer:
    """Advanced volume and volatility analyzer"""

    def __init__(self):
        self.price_levels = 50  # Number of price levels for volume profile
        self.volatility_window = 20
        self.volume_window = 20

    def calculate_volume_profile(self, candles: List[Dict], num_levels: Optional[int] = None) -> VolumeProfile:
        """Calculate volume profile for price levels"""
        if not candles:
            return VolumeProfile(np.array([]), np.array([]), 0.0, 0.0, 0.0, 0.0)

        if num_levels is None:
            num_levels = self.price_levels

        # Extract price and volume data
        highs = np.array([c['high'] for c in candles])
        lows = np.array([c['low'] for c in candles])
        closes = np.array([c['close'] for c in candles])
        volumes = np.array([c['volume'] for c in candles])

        # Create price levels
        price_min = np.min(lows)
        price_max = np.max(highs)
        price_levels = np.linspace(price_min, price_max, num_levels)

        # Calculate volume at each price level
        volume_at_levels = np.zeros(num_levels)

        for i, candle in enumerate(candles):
            # Distribute volume across the candle's price range
            candle_low = candle['low']
            candle_high = candle['high']
            candle_volume = candle['volume']

            # Find price levels within this candle's range
            mask = (price_levels >= candle_low) & (price_levels <= candle_high)
            levels_in_range = np.sum(mask)

            if levels_in_range > 0:
                # Distribute volume evenly across price levels in the candle
                volume_per_level = candle_volume / levels_in_range
                volume_at_levels[mask] += volume_per_level

        # Find Point of Control (POC)
        poc_index = np.argmax(volume_at_levels)
        poc = price_levels[poc_index]

        # Calculate Value Area (70% of volume)
        total_volume = np.sum(volume_at_levels)
        target_volume = total_volume * 0.70

        # Find value area by expanding from POC
        cumulative_volume = volume_at_levels[poc_index]
        low_index = high_index = poc_index

        while cumulative_volume < target_volume and (low_index > 0 or high_index < len(price_levels) - 1):
            # Expand to the side with higher volume
            low_volume = volume_at_levels[low_index - 1] if low_index > 0 else 0
            high_volume = volume_at_levels[high_index + 1] if high_index < len(price_levels) - 1 else 0

            if low_volume >= high_volume and low_index > 0:
                low_index -= 1
                cumulative_volume += volume_at_levels[low_index]
            elif high_index < len(price_levels) - 1:
                high_index += 1
                cumulative_volume += volume_at_levels[high_index]
            else:
                break

        value_area_low = price_levels[low_index]
        value_area_high = price_levels[high_index]
        value_area_volume_pct = cumulative_volume / total_volume if total_volume > 0 else 0

        return VolumeProfile(
            price_levels,
            volume_at_levels,
            poc,
            value_area_high,
            value_area_low,
            value_area_volume_pct
        )

    def calculate_vwap(self, candles: List[Dict]) -> np.ndarray:
        """Calculate Volume Weighted Average Price"""
        if not candles:
            return np.array([])

        typical_prices = np.array([(c['high'] + c['low'] + c['close']) / 3 for c in candles])
        volumes = np.array([c['volume'] for c in candles])

        cumulative_volume = np.cumsum(volumes)
        cumulative_pv = np.cumsum(typical_prices * volumes)

        # Avoid division by zero
        vwap = np.divide(cumulative_pv, cumulative_volume,
                        out=np.zeros_like(cumulative_pv), where=cumulative_volume!=0)

        return vwap

    def analyze_volume_distribution(self, candles: List[Dict]) -> VolumeAnalysis:
        """Comprehensive volume analysis"""
        if len(candles) < self.volume_window:
            return VolumeAnalysis(1.0, 'stable', 'normal', 0.0, 0.0, 0.5)

        volumes = np.array([c['volume'] for c in candles])
        closes = np.array([c['close'] for c in candles])
        highs = np.array([c['high'] for c in candles])
        lows = np.array([c['low'] for c in candles])

        # Relative volume (current vs average)
        recent_volume = np.mean(volumes[-5:])
        avg_volume = np.mean(volumes[:-5]) if len(volumes) > 5 else np.mean(volumes)
        relative_volume = recent_volume / avg_volume if avg_volume > 0 else 1.0

        # Volume trend analysis
        volume_slope = np.polyfit(range(len(volumes)), volumes, 1)[0]
        volume_trend = 'increasing' if volume_slope > avg_volume * 0.01 else \
                      'decreasing' if volume_slope < -avg_volume * 0.01 else 'stable'

        # Volume distribution analysis
        volume_skew = stats.skew(volumes)
        if volume_skew > 1:
            distribution = 'skewed_high'
        elif volume_skew < -1:
            distribution = 'skewed_low'
        else:
            distribution = 'normal'

        # Accumulation/Distribution calculation
        money_flow_multiplier = ((closes - lows) - (highs - closes)) / (highs - lows)
        money_flow_multiplier = np.nan_to_num(money_flow_multiplier, 0.0)
        money_flow_volume = money_flow_multiplier * volumes
        ad_line = np.cumsum(money_flow_volume)
        current_ad = ad_line[-1] if len(ad_line) > 0 else 0.0

        # Volume weighted average price
        vwap = self.calculate_vwap(candles)
        current_vwap = vwap[-1] if len(vwap) > 0 else closes[-1]

        # Volume strength (0-1 scale)
        volume_strength = min(1.0, relative_volume / 2.0)

        return VolumeAnalysis(
            relative_volume,
            volume_trend,
            distribution,
            current_ad,
            current_vwap,
            volume_strength
        )

    def calculate_garman_klass_volatility(self, candles: List[Dict], window: int = 20) -> np.ndarray:
        """Calculate Garman-Klass volatility estimator"""
        if len(candles) < 2:
            return np.array([0.0])

        highs = np.array([c['high'] for c in candles])
        lows = np.array([c['low'] for c in candles])
        opens = np.array([c['open'] for c in candles])
        closes = np.array([c['close'] for c in candles])

        # Garman-Klass estimator
        log_hl = np.log(highs / lows)
        log_co = np.log(closes / opens)

        gk = 0.5 * log_hl**2 - (2*np.log(2) - 1) * log_co**2

        # Rolling window calculation
        gk_volatility = pd.Series(gk).rolling(window=window, min_periods=1).mean().values

        return np.sqrt(gk_volatility * 252)  # Annualized

    def calculate_yang_zhang_volatility(self, candles: List[Dict], window: int = 20) -> np.ndarray:
        """Calculate Yang-Zhang volatility estimator"""
        if len(candles) < 3:
            return np.array([0.0, 0.0])

        highs = np.array([c['high'] for c in candles])
        lows = np.array([c['low'] for c in candles])
        opens = np.array([c['open'] for c in candles])
        closes = np.array([c['close'] for c in candles])

        # Yang-Zhang components
        log_ho = np.log(highs[1:] / opens[1:])
        log_lo = np.log(lows[1:] / opens[1:])
        log_co = np.log(closes[1:] / opens[1:])
        log_oc = np.log(opens[1:] / closes[:-1])

        # Overnight variance
        oc_var = pd.Series(log_oc**2).rolling(window=window, min_periods=1).mean()

        # Open-to-close variance
        yz_co = log_co**2 - log_ho * log_co - log_lo * log_co
        oc_trading_var = pd.Series(yz_co).rolling(window=window, min_periods=1).mean()

        # Yang-Zhang variance
        yz_var = oc_var + oc_trading_var

        # Pad first value
        yz_volatility = np.concatenate([[0.0], np.sqrt(yz_var.values * 252)])

        return yz_volatility

    def detect_volatility_clustering(self, candles: List[Dict], window: int = 20) -> bool:
        """Detect volatility clustering using GARCH-like analysis"""
        if len(candles) < window * 2:
            return False

        closes = np.array([c['close'] for c in candles])
        returns = np.diff(np.log(closes))

        # Calculate rolling volatility
        rolling_vol = pd.Series(returns).rolling(window=window).std()

        # Check for clustering - high volatility followed by high volatility
        high_vol_threshold = np.percentile(rolling_vol.dropna(), 75)
        high_vol_periods = rolling_vol > high_vol_threshold

        # Count consecutive high volatility periods
        clustering_score = 0
        consecutive_count = 0

        for is_high_vol in high_vol_periods:
            if is_high_vol:
                consecutive_count += 1
            else:
                if consecutive_count >= 3:  # 3+ consecutive periods
                    clustering_score += consecutive_count
                consecutive_count = 0

        return clustering_score >= 5  # Threshold for clustering detection

    def analyze_volatility(self, candles: List[Dict]) -> VolatilityAnalysis:
        """Comprehensive volatility analysis"""
        if len(candles) < self.volatility_window:
            return VolatilityAnalysis(0.0, 'normal', False, 0.0, 0.0, 'stable')

        closes = np.array([c['close'] for c in candles])

        # Realized volatility (standard returns volatility)
        returns = np.diff(np.log(closes))
        realized_vol = np.std(returns) * np.sqrt(252)  # Annualized

        # Volatility regime classification
        if realized_vol < 0.15:
            regime = 'low'
        elif realized_vol < 0.30:
            regime = 'normal'
        elif realized_vol < 0.60:
            regime = 'high'
        else:
            regime = 'extreme'

        # Volatility clustering
        clustering = self.detect_volatility_clustering(candles)

        # Garman-Klass volatility
        gk_vol = self.calculate_garman_klass_volatility(candles)
        current_gk_vol = gk_vol[-1] if len(gk_vol) > 0 else 0.0

        # Yang-Zhang volatility
        yz_vol = self.calculate_yang_zhang_volatility(candles)
        current_yz_vol = yz_vol[-1] if len(yz_vol) > 0 else 0.0

        # Volatility trend
        if len(gk_vol) >= 10:
            recent_vol = np.mean(gk_vol[-5:])
            past_vol = np.mean(gk_vol[-10:-5])

            if recent_vol > past_vol * 1.1:
                vol_trend = 'increasing'
            elif recent_vol < past_vol * 0.9:
                vol_trend = 'decreasing'
            else:
                vol_trend = 'stable'
        else:
            vol_trend = 'stable'

        return VolatilityAnalysis(
            realized_vol,
            regime,
            clustering,
            current_gk_vol,
            current_yz_vol,
            vol_trend
        )

    def detect_volume_anomalies(self, candles: List[Dict], z_threshold: float = 3.0) -> List[int]:
        """Detect volume anomalies using statistical methods"""
        if len(candles) < 10:
            return []

        volumes = np.array([c['volume'] for c in candles])

        # Calculate z-scores
        mean_volume = np.mean(volumes)
        std_volume = np.std(volumes)

        if std_volume == 0:
            return []

        z_scores = (volumes - mean_volume) / std_volume

        # Find anomalies
        anomaly_indices = np.where(np.abs(z_scores) > z_threshold)[0]

        return anomaly_indices.tolist()

    def calculate_volume_support_resistance(self, candles: List[Dict]) -> Dict[str, List[float]]:
        """Calculate volume-based support and resistance levels"""
        volume_profile = self.calculate_volume_profile(candles)

        if len(volume_profile.volumes) == 0:
            return {'support': [], 'resistance': []}

        # Find peaks in volume profile
        peaks, _ = find_peaks(volume_profile.volumes, height=np.max(volume_profile.volumes) * 0.3)

        # Get price levels at peaks
        significant_levels = volume_profile.levels[peaks]

        # Current price for classification
        current_price = candles[-1]['close'] if candles else 0

        # Classify as support or resistance
        support_levels = [level for level in significant_levels if level < current_price]
        resistance_levels = [level for level in significant_levels if level > current_price]

        # Sort and take top levels
        support_levels = sorted(support_levels, reverse=True)[:3]  # Top 3 support
        resistance_levels = sorted(resistance_levels)[:3]  # Top 3 resistance

        return {
            'support': support_levels,
            'resistance': resistance_levels
        }

def analyze_comprehensive_volume_volatility(candles: List[Dict]) -> Dict:
    """Comprehensive volume and volatility analysis"""
    analyzer = AdvancedVolumeAnalyzer()

    volume_analysis = analyzer.analyze_volume_distribution(candles)
    volatility_analysis = analyzer.analyze_volatility(candles)
    volume_profile = analyzer.calculate_volume_profile(candles)
    support_resistance = analyzer.calculate_volume_support_resistance(candles)
    volume_anomalies = analyzer.detect_volume_anomalies(candles)

    return {
        'volume_analysis': volume_analysis._asdict(),
        'volatility_analysis': volatility_analysis._asdict(),
        'volume_profile': {
            'poc': volume_profile.poc,
            'value_area_high': volume_profile.value_area_high,
            'value_area_low': volume_profile.value_area_low,
            'value_area_volume_pct': volume_profile.value_area_volume_pct
        },
        'support_resistance': support_resistance,
        'volume_anomalies': volume_anomalies,
        'quality_metrics': {
            'data_points': len(candles),
            'volume_consistency': len(volume_anomalies) / len(candles) if candles else 0,
            'analysis_confidence': min(1.0, len(candles) / 50)
        }
    }