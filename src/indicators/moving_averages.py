"""
Moving Average Indicators
"""

import pandas as pd
import numpy as np
from .base import BaseIndicator


class SMA(BaseIndicator):
    """Simple Moving Average"""

    def __init__(self, period: int = 20, source: str = 'close'):
        """
        Initialize SMA

        Args:
            period: Moving average period
            source: Source column (default: 'close')
        """
        super().__init__(f"SMA_{period}", {'period': period, 'source': source})
        self.period = period
        self.source = source

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Simple Moving Average"""
        if not self.validate_data(df, [self.source]):
            raise ValueError(f"DataFrame missing required column: {self.source}")

        df = df.copy()
        df[self.name] = df[self.source].rolling(window=self.period).mean()
        return df


class EMA(BaseIndicator):
    """Exponential Moving Average"""

    def __init__(self, period: int = 20, source: str = 'close'):
        """
        Initialize EMA

        Args:
            period: Moving average period
            source: Source column (default: 'close')
        """
        super().__init__(f"EMA_{period}", {'period': period, 'source': source})
        self.period = period
        self.source = source

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Exponential Moving Average"""
        if not self.validate_data(df, [self.source]):
            raise ValueError(f"DataFrame missing required column: {self.source}")

        df = df.copy()
        df[self.name] = df[self.source].ewm(span=self.period, adjust=False).mean()
        return df


class WMA(BaseIndicator):
    """Weighted Moving Average"""

    def __init__(self, period: int = 20, source: str = 'close'):
        """
        Initialize WMA

        Args:
            period: Moving average period
            source: Source column (default: 'close')
        """
        super().__init__(f"WMA_{period}", {'period': period, 'source': source})
        self.period = period
        self.source = source

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Weighted Moving Average"""
        if not self.validate_data(df, [self.source]):
            raise ValueError(f"DataFrame missing required column: {self.source}")

        df = df.copy()

        # Calculate weights
        weights = np.arange(1, self.period + 1)

        # Apply weighted moving average
        df[self.name] = df[self.source].rolling(window=self.period).apply(
            lambda x: np.sum(weights * x) / np.sum(weights),
            raw=True
        )

        return df
