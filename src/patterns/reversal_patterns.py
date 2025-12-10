"""
Reversal Pattern Detector
Detects various reversal patterns: double tops/bottoms, head and shoulders, etc.
"""

import pandas as pd
import numpy as np
from typing import List
from datetime import datetime
from .pattern_detector import PatternDetector, PatternResult


class ReversalPatternDetector(PatternDetector):
    """Detects reversal patterns in price data"""

    def __init__(self, min_confidence: float = 0.65, lookback: int = 100):
        """
        Initialize Reversal Pattern Detector

        Args:
            min_confidence: Minimum confidence threshold
            lookback: Number of bars to look back
        """
        super().__init__("Reversal", min_confidence)
        self.lookback = lookback

    def detect(self, df: pd.DataFrame) -> List[PatternResult]:
        """
        Detect all reversal patterns

        Args:
            df: DataFrame with OHLCV data

        Returns:
            List of detected patterns
        """
        if not self.validate_data(df, ['high', 'low', 'close']):
            self.logger.error("DataFrame missing required columns")
            return []

        patterns = []

        # Detect different pattern types
        patterns.extend(self.detect_double_top(df))
        patterns.extend(self.detect_double_bottom(df))
        patterns.extend(self.detect_head_shoulders(df))
        patterns.extend(self.detect_inverse_head_shoulders(df))
        patterns.extend(self.detect_triple_top(df))
        patterns.extend(self.detect_triple_bottom(df))

        # Filter by confidence
        patterns = [p for p in patterns if p.confidence >= self.min_confidence]

        self.logger.info(f"Detected {len(patterns)} reversal patterns")
        return patterns

    def detect_double_top(self, df: pd.DataFrame) -> List[PatternResult]:
        """Detect double top patterns"""
        patterns = []
        highs = df['high']

        # Find peaks
        peaks = self.find_peaks(highs, order=5)

        # Look for double tops
        for i in range(len(peaks) - 1):
            peak1_idx = peaks[i]
            peak2_idx = peaks[i + 1]

            # Check if peaks are similar height
            peak1_price = highs.iloc[peak1_idx]
            peak2_price = highs.iloc[peak2_idx]

            if self.is_similar_price(peak1_price, peak2_price, tolerance=0.015):
                # Find trough between peaks
                between_lows = df['low'].iloc[peak1_idx:peak2_idx]
                if len(between_lows) > 0:
                    trough_idx = peak1_idx + between_lows.idxmin()
                    trough_price = df['low'].iloc[trough_idx]

                    # Calculate confidence
                    price_similarity = 1 - abs(peak1_price - peak2_price) / peak1_price
                    depth_ratio = (peak1_price - trough_price) / peak1_price
                    confidence = (price_similarity * 0.6) + (min(depth_ratio, 0.1) / 0.1 * 0.4)

                    if confidence >= self.min_confidence:
                        pattern = PatternResult(
                            pattern_name="Double Top",
                            confidence=confidence,
                            direction="bearish",
                            start_idx=peak1_idx,
                            end_idx=peak2_idx,
                            start_time=df.index[peak1_idx],
                            end_time=df.index[peak2_idx],
                            key_levels={
                                'peak1': peak1_price,
                                'peak2': peak2_price,
                                'neckline': trough_price
                            },
                            metadata={'pattern_type': 'reversal', 'bars': peak2_idx - peak1_idx}
                        )
                        patterns.append(pattern)

        return patterns

    def detect_double_bottom(self, df: pd.DataFrame) -> List[PatternResult]:
        """Detect double bottom patterns"""
        patterns = []
        lows = df['low']

        # Find troughs
        troughs = self.find_troughs(lows, order=5)

        # Look for double bottoms
        for i in range(len(troughs) - 1):
            trough1_idx = troughs[i]
            trough2_idx = troughs[i + 1]

            # Check if troughs are similar depth
            trough1_price = lows.iloc[trough1_idx]
            trough2_price = lows.iloc[trough2_idx]

            if self.is_similar_price(trough1_price, trough2_price, tolerance=0.015):
                # Find peak between troughs
                between_highs = df['high'].iloc[trough1_idx:trough2_idx]
                if len(between_highs) > 0:
                    peak_idx = trough1_idx + between_highs.idxmax()
                    peak_price = df['high'].iloc[peak_idx]

                    # Calculate confidence
                    price_similarity = 1 - abs(trough1_price - trough2_price) / trough1_price
                    depth_ratio = (peak_price - trough1_price) / trough1_price
                    confidence = (price_similarity * 0.6) + (min(depth_ratio, 0.1) / 0.1 * 0.4)

                    if confidence >= self.min_confidence:
                        pattern = PatternResult(
                            pattern_name="Double Bottom",
                            confidence=confidence,
                            direction="bullish",
                            start_idx=trough1_idx,
                            end_idx=trough2_idx,
                            start_time=df.index[trough1_idx],
                            end_time=df.index[trough2_idx],
                            key_levels={
                                'bottom1': trough1_price,
                                'bottom2': trough2_price,
                                'neckline': peak_price
                            },
                            metadata={'pattern_type': 'reversal', 'bars': trough2_idx - trough1_idx}
                        )
                        patterns.append(pattern)

        return patterns

    def detect_head_shoulders(self, df: pd.DataFrame) -> List[PatternResult]:
        """Detect head and shoulders pattern (bearish)"""
        patterns = []
        highs = df['high']
        peaks = self.find_peaks(highs, order=5)

        # Need at least 3 peaks for head and shoulders
        if len(peaks) < 3:
            return patterns

        for i in range(len(peaks) - 2):
            left_shoulder_idx = peaks[i]
            head_idx = peaks[i + 1]
            right_shoulder_idx = peaks[i + 2]

            left_shoulder = highs.iloc[left_shoulder_idx]
            head = highs.iloc[head_idx]
            right_shoulder = highs.iloc[right_shoulder_idx]

            # Head should be higher than shoulders
            if head > left_shoulder and head > right_shoulder:
                # Shoulders should be similar height
                if self.is_similar_price(left_shoulder, right_shoulder, tolerance=0.02):
                    # Find neckline (lows between peaks)
                    trough1 = df['low'].iloc[left_shoulder_idx:head_idx].min()
                    trough2 = df['low'].iloc[head_idx:right_shoulder_idx].min()
                    neckline = (trough1 + trough2) / 2

                    # Calculate confidence
                    shoulder_similarity = 1 - abs(left_shoulder - right_shoulder) / left_shoulder
                    head_prominence = (head - max(left_shoulder, right_shoulder)) / head
                    confidence = (shoulder_similarity * 0.5) + (min(head_prominence, 0.1) / 0.1 * 0.5)

                    if confidence >= self.min_confidence:
                        pattern = PatternResult(
                            pattern_name="Head and Shoulders",
                            confidence=confidence,
                            direction="bearish",
                            start_idx=left_shoulder_idx,
                            end_idx=right_shoulder_idx,
                            start_time=df.index[left_shoulder_idx],
                            end_time=df.index[right_shoulder_idx],
                            key_levels={
                                'left_shoulder': left_shoulder,
                                'head': head,
                                'right_shoulder': right_shoulder,
                                'neckline': neckline
                            },
                            metadata={'pattern_type': 'reversal', 'bars': right_shoulder_idx - left_shoulder_idx}
                        )
                        patterns.append(pattern)

        return patterns

    def detect_inverse_head_shoulders(self, df: pd.DataFrame) -> List[PatternResult]:
        """Detect inverse head and shoulders pattern (bullish)"""
        patterns = []
        lows = df['low']
        troughs = self.find_troughs(lows, order=5)

        # Need at least 3 troughs
        if len(troughs) < 3:
            return patterns

        for i in range(len(troughs) - 2):
            left_shoulder_idx = troughs[i]
            head_idx = troughs[i + 1]
            right_shoulder_idx = troughs[i + 2]

            left_shoulder = lows.iloc[left_shoulder_idx]
            head = lows.iloc[head_idx]
            right_shoulder = lows.iloc[right_shoulder_idx]

            # Head should be lower than shoulders
            if head < left_shoulder and head < right_shoulder:
                # Shoulders should be similar depth
                if self.is_similar_price(left_shoulder, right_shoulder, tolerance=0.02):
                    # Find neckline (highs between troughs)
                    peak1 = df['high'].iloc[left_shoulder_idx:head_idx].max()
                    peak2 = df['high'].iloc[head_idx:right_shoulder_idx].max()
                    neckline = (peak1 + peak2) / 2

                    # Calculate confidence
                    shoulder_similarity = 1 - abs(left_shoulder - right_shoulder) / left_shoulder
                    head_prominence = (min(left_shoulder, right_shoulder) - head) / head
                    confidence = (shoulder_similarity * 0.5) + (min(head_prominence, 0.1) / 0.1 * 0.5)

                    if confidence >= self.min_confidence:
                        pattern = PatternResult(
                            pattern_name="Inverse Head and Shoulders",
                            confidence=confidence,
                            direction="bullish",
                            start_idx=left_shoulder_idx,
                            end_idx=right_shoulder_idx,
                            start_time=df.index[left_shoulder_idx],
                            end_time=df.index[right_shoulder_idx],
                            key_levels={
                                'left_shoulder': left_shoulder,
                                'head': head,
                                'right_shoulder': right_shoulder,
                                'neckline': neckline
                            },
                            metadata={'pattern_type': 'reversal', 'bars': right_shoulder_idx - left_shoulder_idx}
                        )
                        patterns.append(pattern)

        return patterns

    def detect_triple_top(self, df: pd.DataFrame) -> List[PatternResult]:
        """Detect triple top pattern"""
        patterns = []
        highs = df['high']
        peaks = self.find_peaks(highs, order=5)

        if len(peaks) < 3:
            return patterns

        for i in range(len(peaks) - 2):
            peak1_idx, peak2_idx, peak3_idx = peaks[i], peaks[i+1], peaks[i+2]
            peak1, peak2, peak3 = highs.iloc[peak1_idx], highs.iloc[peak2_idx], highs.iloc[peak3_idx]

            # All peaks should be similar
            if (self.is_similar_price(peak1, peak2, tolerance=0.015) and
                self.is_similar_price(peak2, peak3, tolerance=0.015)):

                neckline = df['low'].iloc[peak1_idx:peak3_idx].min()

                price_similarity = 1 - (max(abs(peak1-peak2), abs(peak2-peak3)) / peak1)
                confidence = price_similarity * 0.8

                if confidence >= self.min_confidence:
                    pattern = PatternResult(
                        pattern_name="Triple Top",
                        confidence=confidence,
                        direction="bearish",
                        start_idx=peak1_idx,
                        end_idx=peak3_idx,
                        start_time=df.index[peak1_idx],
                        end_time=df.index[peak3_idx],
                        key_levels={'peak1': peak1, 'peak2': peak2, 'peak3': peak3, 'neckline': neckline},
                        metadata={'pattern_type': 'reversal', 'bars': peak3_idx - peak1_idx}
                    )
                    patterns.append(pattern)

        return patterns

    def detect_triple_bottom(self, df: pd.DataFrame) -> List[PatternResult]:
        """Detect triple bottom pattern"""
        patterns = []
        lows = df['low']
        troughs = self.find_troughs(lows, order=5)

        if len(troughs) < 3:
            return patterns

        for i in range(len(troughs) - 2):
            trough1_idx, trough2_idx, trough3_idx = troughs[i], troughs[i+1], troughs[i+2]
            trough1, trough2, trough3 = lows.iloc[trough1_idx], lows.iloc[trough2_idx], lows.iloc[trough3_idx]

            # All troughs should be similar
            if (self.is_similar_price(trough1, trough2, tolerance=0.015) and
                self.is_similar_price(trough2, trough3, tolerance=0.015)):

                neckline = df['high'].iloc[trough1_idx:trough3_idx].max()

                price_similarity = 1 - (max(abs(trough1-trough2), abs(trough2-trough3)) / trough1)
                confidence = price_similarity * 0.8

                if confidence >= self.min_confidence:
                    pattern = PatternResult(
                        pattern_name="Triple Bottom",
                        confidence=confidence,
                        direction="bullish",
                        start_idx=trough1_idx,
                        end_idx=trough3_idx,
                        start_time=df.index[trough1_idx],
                        end_time=df.index[trough3_idx],
                        key_levels={'bottom1': trough1, 'bottom2': trough2, 'bottom3': trough3, 'neckline': neckline},
                        metadata={'pattern_type': 'reversal', 'bars': trough3_idx - trough1_idx}
                    )
                    patterns.append(pattern)

        return patterns
