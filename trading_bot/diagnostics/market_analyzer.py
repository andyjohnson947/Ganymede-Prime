"""
Market Analyzer - Analyzes market conditions and price action

Tracks:
- Volatility (ATR, Bollinger Bands)
- Trend strength (ADX, EMA slopes)
- Market regime (trending/ranging/choppy)
- Correlation with trade outcomes
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from datetime import datetime


class MarketAnalyzer:
    """Analyzes market conditions and correlates with performance"""

    def __init__(self):
        """Initialize market analyzer"""
        pass

    def analyze_market_condition(self, price_data: pd.DataFrame) -> Dict:
        """
        Analyze current market condition

        Args:
            price_data: DataFrame with OHLCV data

        Returns:
            Dict with market condition metrics
        """
        if price_data is None or len(price_data) < 50:
            return self._default_condition()

        condition = {}

        # Calculate volatility
        condition['atr'] = self._calculate_atr(price_data)
        condition['bb_width'] = self._calculate_bb_width(price_data)
        condition['volatility_percentile'] = self._get_volatility_percentile(price_data)

        # Calculate trend
        condition['adx'] = self._calculate_adx(price_data)
        condition['ema_slope'] = self._calculate_ema_slope(price_data)
        condition['trend_strength'] = self._classify_trend_strength(condition['adx'])

        # Determine market regime
        condition['regime'] = self._determine_regime(condition)

        # Price action
        condition['price'] = float(price_data['close'].iloc[-1])
        condition['ema_20'] = float(price_data['close'].rolling(20).mean().iloc[-1])
        condition['ema_50'] = float(price_data['close'].rolling(50).mean().iloc[-1])
        condition['price_vs_ema20'] = 'above' if condition['price'] > condition['ema_20'] else 'below'

        return condition

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range"""
        high = df['high']
        low = df['low']
        close = df['close']

        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean().iloc[-1]

        return float(atr) if not np.isnan(atr) else 0.0

    def _calculate_bb_width(self, df: pd.DataFrame, period: int = 20, std: float = 2.0) -> float:
        """Calculate Bollinger Band width (volatility indicator)"""
        sma = df['close'].rolling(period).mean()
        std_dev = df['close'].rolling(period).std()

        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)

        bb_width = ((upper_band - lower_band) / sma * 100).iloc[-1]

        return float(bb_width) if not np.isnan(bb_width) else 0.0

    def _get_volatility_percentile(self, df: pd.DataFrame) -> float:
        """Get current volatility percentile (0-100)"""
        atr_series = []
        for i in range(len(df) - 14):
            window = df.iloc[i:i+14]
            atr_series.append(self._calculate_atr(window))

        if not atr_series:
            return 50.0

        current_atr = self._calculate_atr(df)
        percentile = (sum(1 for x in atr_series if x < current_atr) / len(atr_series)) * 100

        return float(percentile)

    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average Directional Index (trend strength)"""
        high = df['high']
        low = df['low']
        close = df['close']

        # +DM and -DM
        high_diff = high.diff()
        low_diff = -low.diff()

        plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
        minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)

        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Smoothed indicators
        atr = tr.rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)

        # ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(period).mean().iloc[-1]

        return float(adx) if not np.isnan(adx) else 0.0

    def _calculate_ema_slope(self, df: pd.DataFrame, period: int = 50) -> float:
        """Calculate EMA slope (trend direction)"""
        ema = df['close'].ewm(span=period).mean()

        # Calculate slope over last 10 bars
        if len(ema) < 10:
            return 0.0

        recent_ema = ema.iloc[-10:]
        x = np.arange(len(recent_ema))
        slope = np.polyfit(x, recent_ema, 1)[0]

        # Normalize slope (per 10 bars)
        return float(slope)

    def _classify_trend_strength(self, adx: float) -> str:
        """Classify trend strength based on ADX"""
        if adx < 20:
            return 'weak'
        elif adx < 30:
            return 'moderate'
        else:
            return 'strong'

    def _determine_regime(self, condition: Dict) -> str:
        """
        Determine market regime using ADX (matches trading strategy logic)

        ADX-based regime classification:
        - ADX < 20: Ranging (weak trend, mean reversion safe)
        - ADX 20-25: Choppy/Weak trend (transitional)
        - ADX >= 25: Trending (mean reversion blocked by strategy)

        Uses price vs EMA to determine trend direction when trending.

        Returns:
            'trending_up', 'trending_down', 'ranging', or 'choppy'
        """
        adx = condition['adx']
        slope = condition['ema_slope']

        # Ranging market (ADX < 20) - Mean reversion safe
        if adx < 20:
            return 'ranging'

        # Choppy/weak trend (ADX 20-25) - Transitional zone
        if 20 <= adx < 25:
            return 'choppy'

        # Trending market (ADX >= 25) - Strategy blocks mean reversion here
        # Use EMA slope to determine direction
        if adx >= 25:
            if slope > 0:
                return 'trending_up'
            elif slope < 0:
                return 'trending_down'
            else:
                # ADX high but no clear direction - still trending (sideways)
                return 'trending_sideways'

        # Fallback
        return 'ranging'

    def _default_condition(self) -> Dict:
        """Return default condition when insufficient data"""
        return {
            'atr': 0.0,
            'bb_width': 0.0,
            'volatility_percentile': 50.0,
            'adx': 0.0,
            'ema_slope': 0.0,
            'trend_strength': 'unknown',
            'regime': 'unknown',
            'price': 0.0,
            'ema_20': 0.0,
            'ema_50': 0.0,
            'price_vs_ema20': 'unknown',
        }

    def correlate_with_outcome(
        self,
        market_conditions: List[Dict],
        trades: List[Dict]
    ) -> Dict:
        """
        Correlate market conditions with trade outcomes

        Args:
            market_conditions: List of market condition snapshots
            trades: List of trade records

        Returns:
            Dict with correlation insights
        """
        if not trades:
            return {}

        # Group trades by regime
        regime_stats = {}

        for trade in trades:
            regime = trade.get('market_regime', 'unknown')

            if regime not in regime_stats:
                regime_stats[regime] = {'wins': 0, 'losses': 0, 'total_profit': 0.0}

            if trade.get('profit', 0) > 0:
                regime_stats[regime]['wins'] += 1
            else:
                regime_stats[regime]['losses'] += 1

            regime_stats[regime]['total_profit'] += trade.get('profit', 0)

        # Calculate win rates
        correlations = {}
        for regime, stats in regime_stats.items():
            total = stats['wins'] + stats['losses']
            correlations[regime] = {
                'win_rate': (stats['wins'] / total * 100) if total > 0 else 0,
                'total_trades': total,
                'avg_profit': stats['total_profit'] / total if total > 0 else 0,
            }

        return correlations
