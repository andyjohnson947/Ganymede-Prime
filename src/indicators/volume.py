"""
Volume-based Indicators (VWAP, OBV, etc.)
"""

import pandas as pd
import numpy as np
from .base import BaseIndicator


class VWAP(BaseIndicator):
    """Volume-Weighted Average Price"""

    def __init__(self, standard_deviations: list = None):
        """
        Initialize VWAP

        Args:
            standard_deviations: List of std devs for bands (e.g., [1, 2, 3])
        """
        if standard_deviations is None:
            standard_deviations = [1, 2, 3]

        super().__init__("VWAP", {'standard_deviations': standard_deviations})
        self.standard_deviations = standard_deviations

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate VWAP and standard deviation bands"""
        required_cols = ['high', 'low', 'close', 'tick_volume']

        # Try different volume column names
        volume_col = None
        for col in ['tick_volume', 'real_volume', 'volume']:
            if col in df.columns:
                volume_col = col
                break

        if volume_col is None:
            raise ValueError("DataFrame missing volume column")

        if not all(col in df.columns for col in ['high', 'low', 'close']):
            raise ValueError("DataFrame missing required columns: high, low, close")

        df = df.copy()

        # Calculate typical price
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3

        # Calculate VWAP
        df['vwap_cumulative_tpv'] = (df['typical_price'] * df[volume_col]).cumsum()
        df['vwap_cumulative_volume'] = df[volume_col].cumsum()
        df['VWAP'] = df['vwap_cumulative_tpv'] / df['vwap_cumulative_volume']

        # Calculate VWAP standard deviation
        df['vwap_squared_diff'] = ((df['typical_price'] - df['VWAP']) ** 2) * df[volume_col]
        df['vwap_variance'] = df['vwap_squared_diff'].cumsum() / df['vwap_cumulative_volume']
        df['vwap_std'] = np.sqrt(df['vwap_variance'])

        # Calculate standard deviation bands
        for std_dev in self.standard_deviations:
            df[f'VWAP_upper_{std_dev}'] = df['VWAP'] + (std_dev * df['vwap_std'])
            df[f'VWAP_lower_{std_dev}'] = df['VWAP'] - (std_dev * df['vwap_std'])

        # Clean up temporary columns
        temp_cols = ['typical_price', 'vwap_cumulative_tpv', 'vwap_cumulative_volume',
                     'vwap_squared_diff', 'vwap_variance', 'vwap_std']
        df.drop(temp_cols, axis=1, inplace=True, errors='ignore')

        return df


class OBV(BaseIndicator):
    """On-Balance Volume"""

    def __init__(self):
        """Initialize OBV"""
        super().__init__("OBV", {})

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate On-Balance Volume"""
        # Find volume column
        volume_col = None
        for col in ['tick_volume', 'real_volume', 'volume']:
            if col in df.columns:
                volume_col = col
                break

        if volume_col is None or 'close' not in df.columns:
            raise ValueError("DataFrame missing required columns")

        df = df.copy()

        # Calculate OBV
        df['price_change'] = df['close'].diff()
        df['obv_change'] = np.where(df['price_change'] > 0, df[volume_col],
                                     np.where(df['price_change'] < 0, -df[volume_col], 0))
        df['OBV'] = df['obv_change'].cumsum()

        # Clean up temporary columns
        df.drop(['price_change', 'obv_change'], axis=1, inplace=True)

        return df
