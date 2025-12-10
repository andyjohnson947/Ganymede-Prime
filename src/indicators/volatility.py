"""
Volatility Indicators (Bollinger Bands, ATR)
"""

import pandas as pd
import numpy as np
from .base import BaseIndicator


class BollingerBands(BaseIndicator):
    """Bollinger Bands"""

    def __init__(self, period: int = 20, std_dev: float = 2.0, source: str = 'close'):
        """
        Initialize Bollinger Bands

        Args:
            period: Moving average period
            std_dev: Number of standard deviations
            source: Source column (default: 'close')
        """
        super().__init__("BollingerBands", {
            'period': period,
            'std_dev': std_dev,
            'source': source
        })
        self.period = period
        self.std_dev = std_dev
        self.source = source

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Bollinger Bands"""
        if not self.validate_data(df, [self.source]):
            raise ValueError(f"DataFrame missing required column: {self.source}")

        df = df.copy()

        # Calculate middle band (SMA)
        df['BB_middle'] = df[self.source].rolling(window=self.period).mean()

        # Calculate standard deviation
        rolling_std = df[self.source].rolling(window=self.period).std()

        # Calculate upper and lower bands
        df['BB_upper'] = df['BB_middle'] + (rolling_std * self.std_dev)
        df['BB_lower'] = df['BB_middle'] - (rolling_std * self.std_dev)

        # Calculate bandwidth
        df['BB_bandwidth'] = (df['BB_upper'] - df['BB_lower']) / df['BB_middle']

        # Calculate %B (position within bands)
        df['BB_percent'] = (df[self.source] - df['BB_lower']) / (df['BB_upper'] - df['BB_lower'])

        return df


class ATR(BaseIndicator):
    """Average True Range"""

    def __init__(self, period: int = 14):
        """
        Initialize ATR

        Args:
            period: ATR period
        """
        super().__init__(f"ATR_{period}", {'period': period})
        self.period = period

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Average True Range"""
        if not self.validate_data(df, ['high', 'low', 'close']):
            raise ValueError("DataFrame missing required columns: high, low, close")

        df = df.copy()

        # Calculate True Range
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = abs(df['high'] - df['close'].shift(1))
        df['low_close'] = abs(df['low'] - df['close'].shift(1))

        df['true_range'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)

        # Calculate ATR
        df[self.name] = df['true_range'].rolling(window=self.period).mean()

        # Clean up temporary columns
        df.drop(['high_low', 'high_close', 'low_close', 'true_range'], axis=1, inplace=True)

        return df
