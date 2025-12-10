"""
Base Pattern Detector
Abstract class for pattern detection
"""

from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict


@dataclass
class PatternResult:
    """Container for pattern detection results"""
    pattern_name: str
    confidence: float  # 0.0 to 1.0
    direction: str  # 'bullish' or 'bearish'
    start_idx: int
    end_idx: int
    start_time: datetime
    end_time: datetime
    key_levels: Dict[str, float]  # Important price levels
    metadata: Dict  # Additional pattern-specific data


class PatternDetector(ABC):
    """Abstract base class for pattern detection"""

    def __init__(self, name: str, min_confidence: float = 0.65):
        """
        Initialize Pattern Detector

        Args:
            name: Pattern detector name
            min_confidence: Minimum confidence threshold
        """
        self.name = name
        self.min_confidence = min_confidence
        self.logger = logging.getLogger(__name__)

    @abstractmethod
    def detect(self, df: pd.DataFrame) -> List[PatternResult]:
        """
        Detect patterns in the data

        Args:
            df: DataFrame with OHLCV data

        Returns:
            List of PatternResult objects
        """
        pass

    def validate_data(self, df: pd.DataFrame, required_columns: List[str]) -> bool:
        """
        Validate DataFrame has required columns

        Args:
            df: DataFrame to validate
            required_columns: List of required column names

        Returns:
            True if valid, False otherwise
        """
        return all(col in df.columns for col in required_columns)

    def calculate_confidence(self, **metrics) -> float:
        """
        Calculate confidence score based on pattern metrics

        Args:
            **metrics: Pattern-specific metrics

        Returns:
            Confidence score (0.0 to 1.0)
        """
        # Default implementation - can be overridden
        scores = [v for v in metrics.values() if isinstance(v, (int, float))]
        if not scores:
            return 0.5

        # Normalize to 0-1 range
        avg_score = np.mean(scores)
        return max(0.0, min(1.0, avg_score))

    def find_peaks(self, data: pd.Series, order: int = 5) -> np.ndarray:
        """
        Find local peaks in data

        Args:
            data: Series of values
            order: How many points on each side to compare

        Returns:
            Array of peak indices
        """
        peaks = []
        for i in range(order, len(data) - order):
            if all(data.iloc[i] > data.iloc[i-j] for j in range(1, order+1)) and \
               all(data.iloc[i] > data.iloc[i+j] for j in range(1, order+1)):
                peaks.append(i)
        return np.array(peaks)

    def find_troughs(self, data: pd.Series, order: int = 5) -> np.ndarray:
        """
        Find local troughs in data

        Args:
            data: Series of values
            order: How many points on each side to compare

        Returns:
            Array of trough indices
        """
        troughs = []
        for i in range(order, len(data) - order):
            if all(data.iloc[i] < data.iloc[i-j] for j in range(1, order+1)) and \
               all(data.iloc[i] < data.iloc[i+j] for j in range(1, order+1)):
                troughs.append(i)
        return np.array(troughs)

    def is_similar_price(self, price1: float, price2: float, tolerance: float = 0.002) -> bool:
        """
        Check if two prices are similar within tolerance

        Args:
            price1: First price
            price2: Second price
            tolerance: Tolerance as percentage (0.002 = 0.2%)

        Returns:
            True if prices are similar
        """
        if price1 == 0:
            return False
        return abs(price1 - price2) / price1 <= tolerance

    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}', min_confidence={self.min_confidence})"
