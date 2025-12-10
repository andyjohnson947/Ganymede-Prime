"""
Oscillator Indicators (RSI, MACD, Stochastic)
"""

import pandas as pd
import numpy as np
from .base import BaseIndicator


class RSI(BaseIndicator):
    """Relative Strength Index"""

    def __init__(self, period: int = 14, source: str = 'close'):
        """
        Initialize RSI

        Args:
            period: RSI period
            source: Source column (default: 'close')
        """
        super().__init__(f"RSI_{period}", {'period': period, 'source': source})
        self.period = period
        self.source = source

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate RSI"""
        if not self.validate_data(df, [self.source]):
            raise ValueError(f"DataFrame missing required column: {self.source}")

        df = df.copy()

        # Calculate price changes
        delta = df[self.source].diff()

        # Separate gains and losses
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        # Calculate average gain and loss
        avg_gain = gain.rolling(window=self.period).mean()
        avg_loss = loss.rolling(window=self.period).mean()

        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        df[self.name] = 100 - (100 / (1 + rs))

        return df


class MACD(BaseIndicator):
    """Moving Average Convergence Divergence"""

    def __init__(self, fast_period: int = 12, slow_period: int = 26,
                 signal_period: int = 9, source: str = 'close'):
        """
        Initialize MACD

        Args:
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line period
            source: Source column (default: 'close')
        """
        super().__init__("MACD", {
            'fast_period': fast_period,
            'slow_period': slow_period,
            'signal_period': signal_period,
            'source': source
        })
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.source = source

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate MACD"""
        if not self.validate_data(df, [self.source]):
            raise ValueError(f"DataFrame missing required column: {self.source}")

        df = df.copy()

        # Calculate fast and slow EMAs
        fast_ema = df[self.source].ewm(span=self.fast_period, adjust=False).mean()
        slow_ema = df[self.source].ewm(span=self.slow_period, adjust=False).mean()

        # Calculate MACD line
        df['MACD'] = fast_ema - slow_ema

        # Calculate signal line
        df['MACD_signal'] = df['MACD'].ewm(span=self.signal_period, adjust=False).mean()

        # Calculate histogram
        df['MACD_histogram'] = df['MACD'] - df['MACD_signal']

        return df


class Stochastic(BaseIndicator):
    """Stochastic Oscillator"""

    def __init__(self, k_period: int = 14, d_period: int = 3):
        """
        Initialize Stochastic

        Args:
            k_period: %K period
            d_period: %D period (signal line)
        """
        super().__init__("Stochastic", {
            'k_period': k_period,
            'd_period': d_period
        })
        self.k_period = k_period
        self.d_period = d_period

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Stochastic Oscillator"""
        if not self.validate_data(df, ['high', 'low', 'close']):
            raise ValueError("DataFrame missing required columns: high, low, close")

        df = df.copy()

        # Calculate %K
        lowest_low = df['low'].rolling(window=self.k_period).min()
        highest_high = df['high'].rolling(window=self.k_period).max()

        df['Stochastic_K'] = 100 * (df['close'] - lowest_low) / (highest_high - lowest_low)

        # Calculate %D (signal line)
        df['Stochastic_D'] = df['Stochastic_K'].rolling(window=self.d_period).mean()

        return df
