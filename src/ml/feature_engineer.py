"""
Feature Engineering for ML Models
Creates features including ROC, slope, slope acceleration, and flow data
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional
from scipy import stats


class FeatureEngineer:
    """Engineers features for machine learning models"""

    def __init__(self, config: Dict):
        """
        Initialize Feature Engineer

        Args:
            config: ML configuration dictionary
        """
        self.config = config.get('features', {})
        self.logger = logging.getLogger(__name__)

    def engineer_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Engineer all features based on configuration

        Args:
            df: DataFrame with OHLCV data and indicators

        Returns:
            DataFrame with engineered features
        """
        self.logger.info("Engineering features...")

        df = df.copy()

        # Basic features
        df = self._add_basic_features(df)

        # Rate of change features
        df = self._add_roc_features(df)

        # Slope features
        df = self._add_slope_features(df)

        # Slope acceleration (ROC of slope)
        if self.config.get('calculate_slope_acceleration', True):
            df = self._add_slope_acceleration(df)

        # Volume/Flow features
        if self.config.get('use_volume_features', True):
            df = self._add_volume_features(df)

        # Price action features
        if self.config.get('use_price_patterns', True):
            df = self._add_price_action_features(df)

        # Support/Resistance features
        if self.config.get('use_support_resistance', True):
            df = self._add_support_resistance_features(df)

        self.logger.info(f"Feature engineering complete. Total features: {len(df.columns)}")
        return df

    def _add_basic_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add basic price features"""
        # Returns
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))

        # Price range
        df['high_low_range'] = df['high'] - df['low']
        df['high_low_pct'] = (df['high'] - df['low']) / df['close']

        # Body size (candle)
        df['body_size'] = abs(df['close'] - df['open'])
        df['body_size_pct'] = df['body_size'] / df['close']

        # Upper and lower shadows
        df['upper_shadow'] = df['high'] - df[['open', 'close']].max(axis=1)
        df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']

        # Direction
        df['is_bullish'] = (df['close'] > df['open']).astype(int)

        return df

    def _add_roc_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add Rate of Change (ROC) features

        ROC = (Price_current - Price_n_periods_ago) / Price_n_periods_ago * 100
        """
        roc_periods = self.config.get('roc_periods', [5, 10, 20])

        for period in roc_periods:
            # Price ROC
            df[f'roc_{period}'] = df['close'].pct_change(period) * 100

            # High/Low ROC
            df[f'roc_high_{period}'] = df['high'].pct_change(period) * 100
            df[f'roc_low_{period}'] = df['low'].pct_change(period) * 100

        return df

    def _add_slope_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add slope features (linear regression slope over N periods)

        Slope represents the trend strength and direction
        """
        slope_periods = self.config.get('slope_periods', [5, 10, 20])

        for period in slope_periods:
            # Calculate rolling linear regression slope
            df[f'slope_{period}'] = df['close'].rolling(window=period).apply(
                lambda x: self._calculate_slope(x), raw=False
            )

            # Slope of high and low
            df[f'slope_high_{period}'] = df['high'].rolling(window=period).apply(
                lambda x: self._calculate_slope(x), raw=False
            )

            df[f'slope_low_{period}'] = df['low'].rolling(window=period).apply(
                lambda x: self._calculate_slope(x), raw=False
            )

            # Slope angle (in degrees)
            df[f'slope_angle_{period}'] = np.arctan(df[f'slope_{period}']) * (180 / np.pi)

        return df

    def _add_slope_acceleration(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add slope acceleration features (ROC of slope)

        This measures how fast the slope is changing - acceleration/deceleration
        """
        slope_periods = self.config.get('slope_periods', [5, 10, 20])

        for period in slope_periods:
            slope_col = f'slope_{period}'
            if slope_col in df.columns:
                # Slope ROC (acceleration)
                df[f'slope_roc_{period}'] = df[slope_col].pct_change() * 100

                # Slope change
                df[f'slope_change_{period}'] = df[slope_col].diff()

                # Slope momentum (2nd derivative approximation)
                df[f'slope_momentum_{period}'] = df[slope_col].diff(2)

        return df

    def _add_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add volume and flow features
        """
        # Find volume column
        volume_col = self._get_volume_column(df)
        if volume_col is None:
            self.logger.warning("No volume column found, skipping volume features")
            return df

        # Volume ROC
        volume_roc_periods = self.config.get('volume_roc_periods', [5, 10, 20])
        for period in volume_roc_periods:
            df[f'volume_roc_{period}'] = df[volume_col].pct_change(period) * 100

        # Volume acceleration
        if self.config.get('calculate_volume_acceleration', True):
            for period in volume_roc_periods:
                df[f'volume_acceleration_{period}'] = df[f'volume_roc_{period}'].diff()

        # Volume moving averages
        df['volume_ma_20'] = df[volume_col].rolling(window=20).mean()
        df['volume_ratio'] = df[volume_col] / df['volume_ma_20']

        # Money Flow (volume * price)
        df['money_flow'] = df[volume_col] * df['close']
        df['money_flow_ma_20'] = df['money_flow'].rolling(window=20).mean()

        # On-Balance Volume (OBV) changes
        price_change = df['close'].diff()
        df['obv_change'] = np.where(price_change > 0, df[volume_col],
                                     np.where(price_change < 0, -df[volume_col], 0))
        df['obv'] = df['obv_change'].cumsum()
        df['obv_ma_20'] = df['obv'].rolling(window=20).mean()

        # Volume-Price Trend
        df['vpt'] = df[volume_col] * (df['close'].pct_change())
        df['vpt_cumsum'] = df['vpt'].cumsum()

        # Accumulation/Distribution
        df['ad'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / \
                   (df['high'] - df['low']) * df[volume_col]
        df['ad'] = df['ad'].fillna(0)
        df['ad_cumsum'] = df['ad'].cumsum()

        return df

    def _add_price_action_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add price action pattern features"""
        # Doji patterns
        df['is_doji'] = (df['body_size_pct'] < 0.001).astype(int)

        # Hammer/Hanging man
        df['is_hammer'] = (
            (df['lower_shadow'] > 2 * df['body_size']) &
            (df['upper_shadow'] < df['body_size'])
        ).astype(int)

        # Shooting star
        df['is_shooting_star'] = (
            (df['upper_shadow'] > 2 * df['body_size']) &
            (df['lower_shadow'] < df['body_size'])
        ).astype(int)

        # Engulfing patterns
        df['is_bullish_engulfing'] = (
            (df['close'] > df['open']) &  # Current is bullish
            (df['close'].shift(1) < df['open'].shift(1)) &  # Previous is bearish
            (df['open'] < df['close'].shift(1)) &  # Opens below previous close
            (df['close'] > df['open'].shift(1))  # Closes above previous open
        ).astype(int)

        df['is_bearish_engulfing'] = (
            (df['close'] < df['open']) &  # Current is bearish
            (df['close'].shift(1) > df['open'].shift(1)) &  # Previous is bullish
            (df['open'] > df['close'].shift(1)) &  # Opens above previous close
            (df['close'] < df['open'].shift(1))  # Closes below previous open
        ).astype(int)

        # Gap features
        df['gap_up'] = (df['low'] > df['high'].shift(1)).astype(int)
        df['gap_down'] = (df['high'] < df['low'].shift(1)).astype(int)

        # Price vs MA position
        if 'SMA_20' in df.columns:
            df['price_above_sma20'] = (df['close'] > df['SMA_20']).astype(int)
            df['price_distance_from_sma20'] = (df['close'] - df['SMA_20']) / df['SMA_20'] * 100

        if 'SMA_50' in df.columns:
            df['price_above_sma50'] = (df['close'] > df['SMA_50']).astype(int)

        return df

    def _add_support_resistance_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add support and resistance level features"""
        # Rolling high/low (support/resistance levels)
        for period in [20, 50, 100]:
            df[f'resistance_{period}'] = df['high'].rolling(window=period).max()
            df[f'support_{period}'] = df['low'].rolling(window=period).min()

            # Distance to support/resistance
            df[f'distance_to_resistance_{period}'] = \
                (df[f'resistance_{period}'] - df['close']) / df['close'] * 100

            df[f'distance_to_support_{period}'] = \
                (df['close'] - df[f'support_{period}']) / df['close'] * 100

        return df

    def _calculate_slope(self, series: pd.Series) -> float:
        """Calculate linear regression slope"""
        if len(series) < 2:
            return 0.0

        x = np.arange(len(series))
        y = series.values

        if np.all(np.isnan(y)):
            return 0.0

        # Remove NaN values
        mask = ~np.isnan(y)
        if mask.sum() < 2:
            return 0.0

        x = x[mask]
        y = y[mask]

        # Calculate slope using linear regression
        slope, _, _, _, _ = stats.linregress(x, y)
        return slope

    def _get_volume_column(self, df: pd.DataFrame) -> Optional[str]:
        """Find the volume column in DataFrame"""
        for col in ['tick_volume', 'real_volume', 'volume']:
            if col in df.columns:
                return col
        return None

    def get_feature_names(self, df: pd.DataFrame) -> List[str]:
        """
        Get list of feature columns (excluding OHLCV and index)

        Args:
            df: DataFrame with features

        Returns:
            List of feature column names
        """
        exclude_cols = ['open', 'high', 'low', 'close', 'tick_volume', 'real_volume',
                       'volume', 'spread', 'time']

        feature_cols = [col for col in df.columns if col not in exclude_cols]
        return feature_cols

    def get_feature_importance_friendly_names(self) -> Dict[str, str]:
        """
        Get friendly names for features

        Returns:
            Dictionary mapping feature names to descriptions
        """
        return {
            'returns': 'Price Returns',
            'roc_5': 'Rate of Change (5)',
            'roc_10': 'Rate of Change (10)',
            'roc_20': 'Rate of Change (20)',
            'slope_5': 'Price Slope (5)',
            'slope_10': 'Price Slope (10)',
            'slope_20': 'Price Slope (20)',
            'slope_roc_5': 'Slope Acceleration (5)',
            'slope_roc_10': 'Slope Acceleration (10)',
            'slope_roc_20': 'Slope Acceleration (20)',
            'volume_roc_5': 'Volume ROC (5)',
            'volume_roc_10': 'Volume ROC (10)',
            'volume_roc_20': 'Volume ROC (20)',
            'volume_acceleration_5': 'Volume Acceleration (5)',
            'money_flow': 'Money Flow',
            'vpt_cumsum': 'Volume-Price Trend',
            'ad_cumsum': 'Accumulation/Distribution',
            'RSI_14': 'RSI (14)',
            'MACD': 'MACD',
            'BB_percent': 'Bollinger Bands %',
            'ATR_14': 'ATR (14)',
            'VWAP': 'VWAP'
        }
