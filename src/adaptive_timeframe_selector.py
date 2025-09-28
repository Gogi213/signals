"""
SPRINT 2: Adaptive timeframe selection based on market conditions
- Dynamic timeframe adjustment based on volatility and volume
- Multi-timeframe analysis and signal correlation
- Market microstructure analysis for optimal aggregation
- Adaptive signal generation across multiple timeframes
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, NamedTuple, Optional
from scipy import stats
import logging

logger = logging.getLogger(__name__)

class TimeframeAnalysis(NamedTuple):
    """Timeframe analysis result"""
    optimal_timeframe_ms: int
    confidence: float
    market_speed: str  # 'fast', 'medium', 'slow'
    recommended_timeframes: List[int]  # Multiple timeframes to use
    volatility_adjusted: bool

class MultiTimeframeSignal(NamedTuple):
    """Multi-timeframe signal result"""
    primary_signal: bool
    primary_timeframe: int
    secondary_signals: Dict[int, bool]  # timeframe -> signal
    signal_consensus: float  # 0-1, how many timeframes agree
    strength_by_timeframe: Dict[int, float]
    overall_confidence: float

class AdaptiveTimeframeSelector:
    """Adaptive timeframe selector based on market conditions"""

    def __init__(self):
        # Predefined timeframe options (in milliseconds)
        self.base_timeframes = [
            1000,    # 1 second
            2000,    # 2 seconds
            5000,    # 5 seconds
            10000,   # 10 seconds
            15000,   # 15 seconds
            30000,   # 30 seconds
            60000,   # 1 minute
        ]

        self.min_candles_for_analysis = 30
        self.volatility_threshold_low = 0.5
        self.volatility_threshold_high = 2.0

    def analyze_market_microstructure(self, trades: List[Dict]) -> Dict:
        """Analyze market microstructure to determine optimal timeframe"""
        if not trades or len(trades) < 10:
            return {
                'trade_frequency': 0,
                'price_impact': 0,
                'bid_ask_spread_proxy': 0,
                'market_depth_proxy': 0
            }

        # Sort trades by timestamp
        sorted_trades = sorted(trades, key=lambda x: x['timestamp'])

        # Calculate trade frequency (trades per second)
        time_span = (sorted_trades[-1]['timestamp'] - sorted_trades[0]['timestamp']) / 1000
        trade_frequency = len(trades) / time_span if time_span > 0 else 0

        # Price impact analysis
        prices = [trade['price'] for trade in sorted_trades]
        sizes = [trade['size'] for trade in sorted_trades]

        price_changes = np.diff(prices)
        size_weighted_impact = []

        for i in range(len(price_changes)):
            if i < len(sizes) - 1:
                impact = abs(price_changes[i]) * sizes[i+1]
                size_weighted_impact.append(impact)

        avg_price_impact = np.mean(size_weighted_impact) if size_weighted_impact else 0

        # Bid-ask spread proxy (price volatility within short intervals)
        short_intervals = self._group_trades_by_interval(sorted_trades, 1000)  # 1-second intervals
        spread_proxy = 0

        for interval_trades in short_intervals:
            if len(interval_trades) > 1:
                interval_prices = [t['price'] for t in interval_trades]
                price_range = max(interval_prices) - min(interval_prices)
                avg_price = np.mean(interval_prices)
                spread_proxy += price_range / avg_price if avg_price > 0 else 0

        spread_proxy = spread_proxy / len(short_intervals) if short_intervals else 0

        # Market depth proxy (volume consistency)
        volume_cv = np.std(sizes) / np.mean(sizes) if len(sizes) > 0 and np.mean(sizes) > 0 else 0
        market_depth_proxy = 1 / (1 + volume_cv)  # Higher consistency = better depth

        return {
            'trade_frequency': trade_frequency,
            'price_impact': avg_price_impact,
            'bid_ask_spread_proxy': spread_proxy,
            'market_depth_proxy': market_depth_proxy
        }

    def _group_trades_by_interval(self, trades: List[Dict], interval_ms: int) -> List[List[Dict]]:
        """Group trades by time intervals"""
        if not trades:
            return []

        grouped = []
        current_group = []
        current_interval_start = (trades[0]['timestamp'] // interval_ms) * interval_ms

        for trade in trades:
            trade_interval = (trade['timestamp'] // interval_ms) * interval_ms

            if trade_interval == current_interval_start:
                current_group.append(trade)
            else:
                if current_group:
                    grouped.append(current_group)
                current_group = [trade]
                current_interval_start = trade_interval

        if current_group:
            grouped.append(current_group)

        return grouped

    def calculate_optimal_timeframe(self, trades: List[Dict], candles: List[Dict] = None) -> TimeframeAnalysis:
        """Calculate optimal timeframe based on market conditions"""

        if not trades:
            return TimeframeAnalysis(10000, 0.0, 'medium', [10000], False)

        # Analyze market microstructure
        microstructure = self.analyze_market_microstructure(trades)

        # Determine market speed based on trade frequency
        trade_freq = microstructure['trade_frequency']

        if trade_freq > 10:  # More than 10 trades per second
            market_speed = 'fast'
            base_timeframe = 1000  # 1 second
        elif trade_freq > 2:  # 2-10 trades per second
            market_speed = 'medium'
            base_timeframe = 5000  # 5 seconds
        else:  # Less than 2 trades per second
            market_speed = 'slow'
            base_timeframe = 15000  # 15 seconds

        # Adjust for volatility if candles are available
        volatility_adjusted = False
        if candles and len(candles) >= 10:
            closes = np.array([c['close'] for c in candles])
            returns = np.diff(np.log(closes))
            volatility = np.std(returns) * np.sqrt(252) * 100  # Annualized volatility %

            if volatility > self.volatility_threshold_high:
                # High volatility - use shorter timeframes
                base_timeframe = max(1000, base_timeframe // 2)
                volatility_adjusted = True
            elif volatility < self.volatility_threshold_low:
                # Low volatility - can use longer timeframes
                base_timeframe = min(30000, base_timeframe * 2)
                volatility_adjusted = True

        # Price impact adjustment
        if microstructure['price_impact'] > 0.001:  # High price impact
            base_timeframe = max(2000, base_timeframe)  # Use at least 2 seconds

        # Spread adjustment
        if microstructure['bid_ask_spread_proxy'] > 0.002:  # Wide spreads
            base_timeframe = max(5000, base_timeframe)  # Use at least 5 seconds

        # Generate recommended timeframes (multiple for diversification)
        recommended = []

        # Primary timeframe
        recommended.append(base_timeframe)

        # Secondary timeframes
        if base_timeframe >= 5000:
            recommended.append(base_timeframe // 2)  # Shorter
        if base_timeframe <= 15000:
            recommended.append(base_timeframe * 2)  # Longer

        # Ensure we have at least 2 timeframes
        if len(recommended) == 1:
            if base_timeframe == 1000:
                recommended.append(2000)
            else:
                recommended.append(base_timeframe // 2)

        # Calculate confidence based on data quality
        confidence = min(1.0, len(trades) / 100)  # More trades = higher confidence
        confidence *= microstructure['market_depth_proxy']  # Better depth = higher confidence

        return TimeframeAnalysis(
            base_timeframe,
            confidence,
            market_speed,
            sorted(set(recommended)),
            volatility_adjusted
        )

    def generate_multi_timeframe_signals(self, trades: List[Dict]) -> MultiTimeframeSignal:
        """Generate signals across multiple optimal timeframes"""
        from .candle_aggregator import aggregate_trades_to_candles
        from .optimized_signal_processor import OptimizedSignalProcessor

        if not trades:
            return MultiTimeframeSignal(False, 10000, {}, 0.0, {}, 0.0)

        # Get optimal timeframes
        timeframe_analysis = self.calculate_optimal_timeframe(trades)
        timeframes = timeframe_analysis.recommended_timeframes

        processor = OptimizedSignalProcessor()
        signals_by_timeframe = {}
        strengths_by_timeframe = {}

        for timeframe in timeframes:
            try:
                # Aggregate trades for this timeframe
                candles = aggregate_trades_to_candles(trades, timeframe)

                if len(candles) >= processor.min_data_points:
                    # Generate signal for this timeframe
                    signal_result = processor.generate_optimized_signal(candles)
                    signals_by_timeframe[timeframe] = signal_result.signal
                    strengths_by_timeframe[timeframe] = signal_result.strength
                else:
                    # Not enough data for reliable signal
                    signals_by_timeframe[timeframe] = False
                    strengths_by_timeframe[timeframe] = 0.0

            except Exception as e:
                logger.warning(f"Error generating signal for timeframe {timeframe}: {e}")
                signals_by_timeframe[timeframe] = False
                strengths_by_timeframe[timeframe] = 0.0

        # Determine primary signal (from optimal timeframe)
        primary_timeframe = timeframe_analysis.optimal_timeframe_ms
        primary_signal = signals_by_timeframe.get(primary_timeframe, False)

        # Calculate signal consensus
        if signals_by_timeframe:
            consensus = sum(signals_by_timeframe.values()) / len(signals_by_timeframe)
        else:
            consensus = 0.0

        # Calculate overall confidence
        # Weight by timeframe analysis confidence and signal consensus
        base_confidence = timeframe_analysis.confidence
        consensus_confidence = consensus if consensus > 0.5 else (1 - consensus)
        overall_confidence = (base_confidence + consensus_confidence) / 2

        # Separate secondary signals (exclude primary)
        secondary_signals = {tf: signal for tf, signal in signals_by_timeframe.items()
                           if tf != primary_timeframe}

        return MultiTimeframeSignal(
            primary_signal,
            primary_timeframe,
            secondary_signals,
            consensus,
            strengths_by_timeframe,
            overall_confidence
        )

    def analyze_timeframe_performance(self, trades: List[Dict],
                                    historical_results: Dict[int, List[bool]] = None) -> Dict:
        """Analyze performance of different timeframes"""

        if not historical_results:
            return {'optimal_timeframe': 10000, 'performance_metrics': {}}

        performance_metrics = {}

        for timeframe, results in historical_results.items():
            if results:
                accuracy = sum(results) / len(results)
                consistency = 1 - np.std([int(r) for r in results])

                # Combined score
                score = (accuracy * 0.7) + (consistency * 0.3)

                performance_metrics[timeframe] = {
                    'accuracy': accuracy,
                    'consistency': consistency,
                    'score': score,
                    'sample_size': len(results)
                }

        # Find best performing timeframe
        if performance_metrics:
            best_timeframe = max(performance_metrics.keys(),
                               key=lambda tf: performance_metrics[tf]['score'])
        else:
            best_timeframe = 10000  # Default

        return {
            'optimal_timeframe': best_timeframe,
            'performance_metrics': performance_metrics
        }

    def recommend_timeframe_strategy(self, trades: List[Dict],
                                   market_conditions: Dict = None) -> Dict:
        """Recommend comprehensive timeframe strategy"""

        # Get basic timeframe analysis
        analysis = self.calculate_optimal_timeframe(trades)

        # Get multi-timeframe signals
        multi_signal = self.generate_multi_timeframe_signals(trades)

        # Market condition adjustments
        strategy_adjustments = []

        if market_conditions:
            if market_conditions.get('volatility_regime') == 'high':
                strategy_adjustments.append("Use shorter timeframes during high volatility")

            if market_conditions.get('volume_regime') == 'low':
                strategy_adjustments.append("Consider longer timeframes during low volume")

            if market_conditions.get('trend_strength', 0) > 0.8:
                strategy_adjustments.append("Use trend-following timeframes during strong trends")

        return {
            'primary_recommendation': {
                'timeframe_ms': analysis.optimal_timeframe_ms,
                'timeframe_seconds': analysis.optimal_timeframe_ms / 1000,
                'confidence': analysis.confidence,
                'market_speed': analysis.market_speed
            },
            'multi_timeframe_approach': {
                'recommended_timeframes': analysis.recommended_timeframes,
                'signal_consensus': multi_signal.signal_consensus,
                'overall_confidence': multi_signal.overall_confidence
            },
            'strategy_adjustments': strategy_adjustments,
            'market_analysis': {
                'volatility_adjusted': analysis.volatility_adjusted,
                'microstructure_quality': len(trades) >= 50
            }
        }

def select_optimal_timeframe_for_trades(trades: List[Dict]) -> Dict:
    """Main function to select optimal timeframe for given trades"""
    selector = AdaptiveTimeframeSelector()

    # Get timeframe analysis
    analysis = selector.calculate_optimal_timeframe(trades)

    # Get multi-timeframe signals
    multi_signal = selector.generate_multi_timeframe_signals(trades)

    # Prepare comprehensive result
    return {
        'optimal_timeframe_ms': analysis.optimal_timeframe_ms,
        'confidence': analysis.confidence,
        'market_speed': analysis.market_speed,
        'recommended_timeframes': analysis.recommended_timeframes,
        'multi_timeframe_signal': {
            'primary_signal': multi_signal.primary_signal,
            'signal_consensus': multi_signal.signal_consensus,
            'overall_confidence': multi_signal.overall_confidence,
            'signals_by_timeframe': {
                **{multi_signal.primary_timeframe: multi_signal.primary_signal},
                **multi_signal.secondary_signals
            }
        },
        'metadata': {
            'trade_count': len(trades),
            'analysis_quality': 'high' if len(trades) >= 100 else 'medium' if len(trades) >= 50 else 'low'
        }
    }