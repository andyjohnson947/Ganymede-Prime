"""
Base Indicator Class
All indicators inherit from this class for consistency
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any


class BaseIndicator(ABC):
    """Abstract base class for all technical indicators"""

    def __init__(self, name: str, params: Dict[str, Any] = None):
        """
        Initialize base indicator

        Args:
            name: Indicator name
            params: Dictionary of parameters
        """
        self.name = name
        self.params = params or {}

    @abstractmethod
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicator values

        Args:
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with indicator columns added
        """
        pass

    def validate_data(self, df: pd.DataFrame, required_columns: list) -> bool:
        """
        Validate that DataFrame has required columns

        Args:
            df: DataFrame to validate
            required_columns: List of required column names

        Returns:
            True if valid, False otherwise
        """
        return all(col in df.columns for col in required_columns)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name}, params={self.params})"
