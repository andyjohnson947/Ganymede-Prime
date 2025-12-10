"""
Indicator Manager
Manages multiple indicators and applies them to data
"""

import pandas as pd
import logging
from typing import List, Dict, Any
from .base import BaseIndicator
from .moving_averages import SMA, EMA, WMA
from .oscillators import RSI, MACD, Stochastic
from .volatility import BollingerBands, ATR
from .volume import VWAP, OBV


class IndicatorManager:
    """Manages and applies multiple technical indicators"""

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize Indicator Manager

        Args:
            config: Configuration dictionary for indicators
        """
        self.config = config or {}
        self.indicators: List[BaseIndicator] = []
        self.logger = logging.getLogger(__name__)

        # Initialize indicators from config
        self._initialize_from_config()

    def _initialize_from_config(self):
        """Initialize indicators based on configuration"""
        indicators_config = self.config.get('indicators', {})

        # VWAP
        if indicators_config.get('vwap', {}).get('enabled', False):
            std_devs = indicators_config['vwap'].get('standard_deviations', [1, 2, 3])
            self.add_indicator(VWAP(standard_deviations=std_devs))

        # Moving Averages
        if indicators_config.get('moving_averages', {}).get('enabled', False):
            ma_config = indicators_config['moving_averages']
            periods = ma_config.get('periods', [20, 50, 200])
            ma_types = ma_config.get('types', ['SMA', 'EMA'])

            for period in periods:
                if 'SMA' in ma_types:
                    self.add_indicator(SMA(period=period))
                if 'EMA' in ma_types:
                    self.add_indicator(EMA(period=period))

        # RSI
        if indicators_config.get('rsi', {}).get('enabled', False):
            period = indicators_config['rsi'].get('period', 14)
            self.add_indicator(RSI(period=period))

        # MACD
        if indicators_config.get('macd', {}).get('enabled', False):
            macd_config = indicators_config['macd']
            self.add_indicator(MACD(
                fast_period=macd_config.get('fast_period', 12),
                slow_period=macd_config.get('slow_period', 26),
                signal_period=macd_config.get('signal_period', 9)
            ))

        # Bollinger Bands
        if indicators_config.get('bollinger_bands', {}).get('enabled', False):
            bb_config = indicators_config['bollinger_bands']
            self.add_indicator(BollingerBands(
                period=bb_config.get('period', 20),
                std_dev=bb_config.get('std_dev', 2)
            ))

        # ATR
        if indicators_config.get('atr', {}).get('enabled', False):
            period = indicators_config['atr'].get('period', 14)
            self.add_indicator(ATR(period=period))

        # Stochastic
        if indicators_config.get('stochastic', {}).get('enabled', False):
            stoch_config = indicators_config['stochastic']
            self.add_indicator(Stochastic(
                k_period=stoch_config.get('k_period', 14),
                d_period=stoch_config.get('d_period', 3)
            ))

        self.logger.info(f"Initialized {len(self.indicators)} indicators from config")

    def add_indicator(self, indicator: BaseIndicator):
        """
        Add an indicator to the manager

        Args:
            indicator: BaseIndicator instance
        """
        self.indicators.append(indicator)
        self.logger.debug(f"Added indicator: {indicator}")

    def remove_indicator(self, indicator_name: str):
        """
        Remove an indicator by name

        Args:
            indicator_name: Name of indicator to remove
        """
        self.indicators = [ind for ind in self.indicators if ind.name != indicator_name]
        self.logger.debug(f"Removed indicator: {indicator_name}")

    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all indicators on the given DataFrame

        Args:
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with all indicator columns added
        """
        df = df.copy()

        for indicator in self.indicators:
            try:
                df = indicator.calculate(df)
                self.logger.debug(f"Calculated {indicator.name}")
            except Exception as e:
                self.logger.error(f"Error calculating {indicator.name}: {e}")

        return df

    def get_indicator_names(self) -> List[str]:
        """
        Get list of all indicator names

        Returns:
            List of indicator names
        """
        return [ind.name for ind in self.indicators]

    def get_indicator(self, name: str) -> BaseIndicator:
        """
        Get indicator by name

        Args:
            name: Indicator name

        Returns:
            BaseIndicator instance or None
        """
        for indicator in self.indicators:
            if indicator.name == name:
                return indicator
        return None

    def __len__(self):
        return len(self.indicators)

    def __repr__(self):
        return f"IndicatorManager({len(self.indicators)} indicators)"
