"""
Volume Expansion Analyzer
Detects volume surges and patterns for breakout confirmation

CRITICAL for breakout strategy: Volume confirms real breakouts vs false breakouts
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List


class VolumeAnalyzer:
    """
    Analyzes volume patterns for breakout validation

    Features:
    - Volume percentile calculation (vs recent average)
    - Volume expansion detection (surges)
    - Volume moving averages
    - Volume profile integration
    - Relative volume analysis
    """

    def __init__(self, lookback: int = 20):
        """
        Initialize volume analyzer

        Args:
            lookback: Number of periods for volume comparison
        """
        self.lookback = lookback

    def calculate_volume_percentile(
        self,
        data: pd.DataFrame,
        volume_col: str = 'tick_volume'
    ) -> float:
        """
        Calculate current volume percentile vs recent average

        Args:
            data: OHLC data with volume
            volume_col: Volume column name

        Returns:
            Volume percentile (0-100)
        """
        if volume_col not in data.columns:
            # Try alternative volume column
            if 'volume' in data.columns:
                volume_col = 'volume'
            elif 'real_volume' in data.columns:
                volume_col = 'real_volume'
            else:
                return 50.0  # Default if no volume data

        if len(data) < self.lookback:
            return 50.0  # Not enough data

        recent = data.tail(self.lookback)
        current_volume = data.iloc[-1][volume_col]

        # Calculate percentile rank
        volume_rank = (recent[volume_col] < current_volume).sum()
        percentile = (volume_rank / len(recent)) * 100

        return percentile

    def detect_volume_expansion(
        self,
        data: pd.DataFrame,
        threshold: float = 1.5,
        volume_col: str = 'tick_volume'
    ) -> Dict:
        """
        Detect volume expansion (surge above average)

        Args:
            data: OHLC data with volume
            threshold: Multiplier for expansion (1.5 = 150% of average)
            volume_col: Volume column name

        Returns:
            Dict with expansion analysis
        """
        if volume_col not in data.columns:
            if 'volume' in data.columns:
                volume_col = 'volume'
            elif 'real_volume' in data.columns:
                volume_col = 'real_volume'
            else:
                return {
                    'is_expansion': False,
                    'ratio': 1.0,
                    'percentile': 50.0,
                }

        if len(data) < self.lookback:
            return {
                'is_expansion': False,
                'ratio': 1.0,
                'percentile': 50.0,
            }

        recent = data.tail(self.lookback)
        current_volume = data.iloc[-1][volume_col]
        avg_volume = recent[volume_col].mean()

        # Calculate volume ratio
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        # Calculate percentile
        percentile = self.calculate_volume_percentile(data, volume_col)

        # Determine if expansion
        is_expansion = volume_ratio >= threshold

        # Classify strength
        if volume_ratio >= 2.0:
            strength = 'very_strong'
        elif volume_ratio >= 1.8:
            strength = 'strong'
        elif volume_ratio >= 1.5:
            strength = 'moderate'
        elif volume_ratio >= 1.3:
            strength = 'weak'
        else:
            strength = 'none'

        return {
            'is_expansion': is_expansion,
            'ratio': volume_ratio,
            'percentile': percentile,
            'current': current_volume,
            'average': avg_volume,
            'strength': strength,
        }

    def calculate_volume_ma(
        self,
        data: pd.DataFrame,
        period: int = 20,
        volume_col: str = 'tick_volume'
    ) -> pd.Series:
        """
        Calculate volume moving average

        Args:
            data: OHLC data with volume
            period: MA period
            volume_col: Volume column name

        Returns:
            Series with volume MA
        """
        if volume_col not in data.columns:
            if 'volume' in data.columns:
                volume_col = 'volume'
            else:
                return pd.Series([0] * len(data))

        return data[volume_col].rolling(window=period).mean()

    def detect_volume_climax(
        self,
        data: pd.DataFrame,
        threshold: float = 2.0,
        volume_col: str = 'tick_volume'
    ) -> bool:
        """
        Detect volume climax (extreme surge)

        Often indicates exhaustion or major breakout

        Args:
            data: OHLC data with volume
            threshold: Multiplier for climax (2.0 = 200% of average)
            volume_col: Volume column name

        Returns:
            True if volume climax detected
        """
        expansion = self.detect_volume_expansion(data, threshold, volume_col)
        return expansion['is_expansion'] and expansion['ratio'] >= threshold

    def analyze_volume_trend(
        self,
        data: pd.DataFrame,
        periods: int = 5,
        volume_col: str = 'tick_volume'
    ) -> Dict:
        """
        Analyze volume trend (increasing/decreasing)

        Args:
            data: OHLC data with volume
            periods: Number of periods to analyze
            volume_col: Volume column name

        Returns:
            Dict with trend analysis
        """
        if volume_col not in data.columns:
            if 'volume' in data.columns:
                volume_col = 'volume'
            else:
                return {'trend': 'unknown', 'increasing': False}

        if len(data) < periods:
            return {'trend': 'unknown', 'increasing': False}

        recent = data.tail(periods)[volume_col].values

        # Count increasing vs decreasing bars
        increasing = sum(recent[i] > recent[i-1] for i in range(1, len(recent)))
        decreasing = sum(recent[i] < recent[i-1] for i in range(1, len(recent)))

        # Determine trend
        if increasing > decreasing + 1:
            trend = 'increasing'
        elif decreasing > increasing + 1:
            trend = 'decreasing'
        else:
            trend = 'neutral'

        return {
            'trend': trend,
            'increasing': trend == 'increasing',
            'decreasing': trend == 'decreasing',
            'increasing_bars': increasing,
            'decreasing_bars': decreasing,
        }

    def calculate_relative_volume(
        self,
        data: pd.DataFrame,
        timeframe: str = 'H1',
        volume_col: str = 'tick_volume'
    ) -> Dict:
        """
        Calculate relative volume (current vs typical for time of day)

        Args:
            data: OHLC data with volume
            timeframe: Timeframe (for time-of-day analysis)
            volume_col: Volume column name

        Returns:
            Dict with relative volume analysis
        """
        if volume_col not in data.columns:
            if 'volume' in data.columns:
                volume_col = 'volume'
            else:
                return {'relative_volume': 1.0, 'interpretation': 'unknown'}

        # Basic relative volume (vs simple average)
        # TODO: Enhance with time-of-day awareness for more accurate relative volume
        expansion = self.detect_volume_expansion(data, threshold=1.0, volume_col=volume_col)

        return {
            'relative_volume': expansion['ratio'],
            'percentile': expansion['percentile'],
            'interpretation': expansion['strength'],
        }

    def validate_breakout_volume(
        self,
        data: pd.DataFrame,
        min_percentile: float = 70,
        min_ratio: float = 1.5,
        volume_col: str = 'tick_volume'
    ) -> Dict:
        """
        Validate if volume is sufficient for breakout confirmation

        CRITICAL: This is the main validation for breakout signals

        Args:
            data: OHLC data with volume
            min_percentile: Minimum volume percentile required
            min_ratio: Minimum volume ratio required
            volume_col: Volume column name

        Returns:
            Dict with validation result
        """
        expansion = self.detect_volume_expansion(data, threshold=min_ratio, volume_col=volume_col)
        percentile = expansion['percentile']

        # Check if meets requirements
        meets_percentile = percentile >= min_percentile
        meets_ratio = expansion['ratio'] >= min_ratio

        valid = meets_percentile or meets_ratio  # Either condition is sufficient

        # Determine quality
        if percentile >= 80 and expansion['ratio'] >= 1.8:
            quality = 'excellent'
        elif percentile >= 70 and expansion['ratio'] >= 1.5:
            quality = 'good'
        elif percentile >= 60 or expansion['ratio'] >= 1.3:
            quality = 'acceptable'
        else:
            quality = 'weak'

        return {
            'valid': valid,
            'quality': quality,
            'percentile': percentile,
            'ratio': expansion['ratio'],
            'current': expansion['current'],
            'average': expansion['average'],
            'meets_percentile': meets_percentile,
            'meets_ratio': meets_ratio,
            'recommendation': 'CONFIRM' if valid else 'REJECT',
        }

    def detect_volume_divergence(
        self,
        data: pd.DataFrame,
        price_col: str = 'close',
        volume_col: str = 'tick_volume',
        periods: int = 10
    ) -> Dict:
        """
        Detect volume-price divergence

        Divergence can indicate weakening trend or reversal

        Args:
            data: OHLC data with volume
            price_col: Price column to compare
            volume_col: Volume column name
            periods: Number of periods to analyze

        Returns:
            Dict with divergence analysis
        """
        if len(data) < periods or volume_col not in data.columns:
            return {'divergence': False, 'type': 'none'}

        recent = data.tail(periods)

        # Calculate price direction
        price_change = recent[price_col].iloc[-1] - recent[price_col].iloc[0]
        price_direction = 'up' if price_change > 0 else 'down'

        # Calculate volume trend
        volume_trend = self.analyze_volume_trend(recent, periods=periods, volume_col=volume_col)

        # Detect divergence
        # Bullish divergence: Price down but volume increasing
        # Bearish divergence: Price up but volume decreasing
        if price_direction == 'down' and volume_trend['increasing']:
            divergence_type = 'bullish'
            divergence = True
        elif price_direction == 'up' and volume_trend['decreasing']:
            divergence_type = 'bearish'
            divergence = True
        else:
            divergence_type = 'none'
            divergence = False

        return {
            'divergence': divergence,
            'type': divergence_type,
            'price_direction': price_direction,
            'volume_trend': volume_trend['trend'],
            'strength': 'strong' if abs(volume_trend['increasing_bars'] - volume_trend['decreasing_bars']) > 3 else 'weak',
        }

    def get_volume_summary(
        self,
        data: pd.DataFrame,
        volume_col: str = 'tick_volume'
    ) -> Dict:
        """
        Get comprehensive volume summary for current bar

        Args:
            data: OHLC data with volume
            volume_col: Volume column name

        Returns:
            Dict with complete volume analysis
        """
        if volume_col not in data.columns:
            if 'volume' in data.columns:
                volume_col = 'volume'
            else:
                return {'error': 'No volume data available'}

        expansion = self.detect_volume_expansion(data, volume_col=volume_col)
        trend = self.analyze_volume_trend(data, volume_col=volume_col)
        validation = self.validate_breakout_volume(data, volume_col=volume_col)
        climax = self.detect_volume_climax(data, volume_col=volume_col)

        return {
            'current_volume': expansion['current'],
            'average_volume': expansion['average'],
            'volume_ratio': expansion['ratio'],
            'percentile': expansion['percentile'],
            'is_expansion': expansion['is_expansion'],
            'expansion_strength': expansion['strength'],
            'volume_trend': trend['trend'],
            'is_climax': climax,
            'breakout_validation': validation,
            'summary': f"{expansion['strength'].upper()} volume ({expansion['percentile']:.0f}th percentile, {expansion['ratio']:.2f}x avg)",
        }


def format_volume_summary(summary: Dict) -> str:
    """
    Format volume summary for logging/display

    Args:
        summary: Volume summary dict from get_volume_summary()

    Returns:
        Formatted string
    """
    if 'error' in summary:
        return f"⚠️  {summary['error']}"

    emoji = "🔥" if summary['is_climax'] else "📊"
    validation = "✅" if summary['breakout_validation']['valid'] else "❌"

    text = (
        f"{emoji} Volume: {summary['percentile']:.0f}th percentile | "
        f"{summary['volume_ratio']:.2f}x avg | "
        f"Trend: {summary['volume_trend']} | "
        f"Breakout validation: {validation} {summary['breakout_validation']['quality'].upper()}"
    )

    return text
