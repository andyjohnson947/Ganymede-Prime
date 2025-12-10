"""
Market Profile Calculator
Calculates POC, VAH, VAL, and volume profiles
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class VolumeProfile:
    """Container for volume profile results"""
    vwap: float
    poc: float  # Point of Control (price with highest volume)
    vah: float  # Value Area High
    val: float  # Value Area Low
    total_volume: float
    value_area_volume: float
    price_levels: pd.DataFrame  # DataFrame with price levels and volumes


class MarketProfileCalculator:
    """Calculates market profile metrics"""

    def __init__(self, value_area_percentage: float = 70.0, price_tick_size: float = 0.0001):
        """
        Initialize Market Profile Calculator

        Args:
            value_area_percentage: Percentage of volume for value area (default 70%)
            price_tick_size: Minimum price increment for grouping
        """
        self.value_area_percentage = value_area_percentage
        self.price_tick_size = price_tick_size
        self.logger = logging.getLogger(__name__)

    def calculate_profile(self, df: pd.DataFrame) -> Optional[VolumeProfile]:
        """
        Calculate complete market profile

        Args:
            df: DataFrame with OHLCV data

        Returns:
            VolumeProfile object or None if error
        """
        try:
            # Find volume column
            volume_col = self._get_volume_column(df)
            if volume_col is None:
                self.logger.error("No volume column found")
                return None

            # Calculate VWAP
            vwap = self._calculate_vwap(df, volume_col)

            # Build volume profile
            price_levels = self._build_volume_profile(df, volume_col)

            if price_levels.empty:
                self.logger.error("Failed to build volume profile")
                return None

            # Calculate POC (Point of Control)
            poc = price_levels.loc[price_levels['volume'].idxmax(), 'price']

            # Calculate Value Area (VAH and VAL)
            vah, val, value_area_volume = self._calculate_value_area(price_levels)

            # Total volume
            total_volume = price_levels['volume'].sum()

            profile = VolumeProfile(
                vwap=vwap,
                poc=poc,
                vah=vah,
                val=val,
                total_volume=total_volume,
                value_area_volume=value_area_volume,
                price_levels=price_levels
            )

            self.logger.info(f"Profile calculated - VWAP: {vwap:.5f}, POC: {poc:.5f}, "
                           f"VAH: {vah:.5f}, VAL: {val:.5f}")

            return profile

        except Exception as e:
            self.logger.error(f"Error calculating profile: {e}")
            return None

    def _get_volume_column(self, df: pd.DataFrame) -> Optional[str]:
        """Find the volume column in DataFrame"""
        for col in ['tick_volume', 'real_volume', 'volume']:
            if col in df.columns:
                return col
        return None

    def _calculate_vwap(self, df: pd.DataFrame, volume_col: str) -> float:
        """
        Calculate Volume-Weighted Average Price

        Args:
            df: DataFrame with OHLCV data
            volume_col: Name of volume column

        Returns:
            VWAP value
        """
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df[volume_col]).sum() / df[volume_col].sum()
        return vwap

    def _build_volume_profile(self, df: pd.DataFrame, volume_col: str) -> pd.DataFrame:
        """
        Build volume profile by aggregating volume at price levels

        Args:
            df: DataFrame with OHLCV data
            volume_col: Name of volume column

        Returns:
            DataFrame with price levels and aggregated volumes
        """
        # Create price levels from high and low
        price_data = []

        for idx, row in df.iterrows():
            # Calculate number of price levels between high and low
            price_range = row['high'] - row['low']
            if price_range == 0:
                # Single price point
                price_data.append({
                    'price': row['close'],
                    'volume': row[volume_col]
                })
            else:
                # Distribute volume across price range
                # Assume uniform distribution for simplicity
                num_levels = max(1, int(price_range / self.price_tick_size))
                volume_per_level = row[volume_col] / num_levels

                for i in range(num_levels):
                    price = row['low'] + (i * self.price_tick_size)
                    price_data.append({
                        'price': price,
                        'volume': volume_per_level
                    })

        # Create DataFrame and group by price
        profile_df = pd.DataFrame(price_data)

        # Round prices to tick size
        profile_df['price'] = (profile_df['price'] / self.price_tick_size).round() * self.price_tick_size

        # Aggregate volume by price level
        profile_df = profile_df.groupby('price', as_index=False).agg({'volume': 'sum'})
        profile_df = profile_df.sort_values('price')

        return profile_df

    def _calculate_value_area(self, price_levels: pd.DataFrame) -> Tuple[float, float, float]:
        """
        Calculate Value Area High (VAH) and Value Area Low (VAL)

        The value area contains X% of the total volume (typically 70%)
        centered around the POC

        Args:
            price_levels: DataFrame with price and volume columns

        Returns:
            Tuple of (VAH, VAL, value_area_volume)
        """
        # Find POC (price with highest volume)
        poc_idx = price_levels['volume'].idxmax()

        # Calculate target volume for value area
        total_volume = price_levels['volume'].sum()
        target_volume = total_volume * (self.value_area_percentage / 100.0)

        # Start from POC and expand up and down
        included_indices = {poc_idx}
        current_volume = price_levels.loc[poc_idx, 'volume']

        # Get sorted indices
        sorted_indices = price_levels.index.tolist()
        poc_position = sorted_indices.index(poc_idx)

        upper_idx = poc_position + 1
        lower_idx = poc_position - 1

        # Expand value area until we reach target volume
        while current_volume < target_volume:
            upper_volume = 0
            lower_volume = 0

            # Check volumes above and below
            if upper_idx < len(sorted_indices):
                upper_volume = price_levels.loc[sorted_indices[upper_idx], 'volume']

            if lower_idx >= 0:
                lower_volume = price_levels.loc[sorted_indices[lower_idx], 'volume']

            # Add the side with higher volume
            if upper_volume == 0 and lower_volume == 0:
                break

            if upper_volume >= lower_volume and upper_idx < len(sorted_indices):
                included_indices.add(sorted_indices[upper_idx])
                current_volume += upper_volume
                upper_idx += 1
            elif lower_idx >= 0:
                included_indices.add(sorted_indices[lower_idx])
                current_volume += lower_volume
                lower_idx -= 1
            else:
                break

        # Calculate VAH and VAL
        value_area_prices = price_levels.loc[list(included_indices), 'price']
        vah = value_area_prices.max()
        val = value_area_prices.min()

        return vah, val, current_volume

    def calculate_daily_profile(self, df: pd.DataFrame, date: datetime) -> Optional[VolumeProfile]:
        """
        Calculate market profile for a specific day

        Args:
            df: DataFrame with OHLCV data (time as index)
            date: Date to calculate profile for

        Returns:
            VolumeProfile object or None
        """
        # Filter data for the specific date
        daily_data = df[df.index.date == date.date()]

        if daily_data.empty:
            self.logger.warning(f"No data found for date {date.date()}")
            return None

        return self.calculate_profile(daily_data)

    def calculate_session_profile(
        self,
        df: pd.DataFrame,
        session_start: str = "09:30",
        session_end: str = "16:00"
    ) -> Optional[VolumeProfile]:
        """
        Calculate market profile for a trading session

        Args:
            df: DataFrame with OHLCV data (time as index)
            session_start: Session start time (HH:MM)
            session_end: Session end time (HH:MM)

        Returns:
            VolumeProfile object or None
        """
        # Filter data for session times
        session_data = df.between_time(session_start, session_end)

        if session_data.empty:
            self.logger.warning(f"No data found for session {session_start}-{session_end}")
            return None

        return self.calculate_profile(session_data)

    def get_profile_summary(self, profile: VolumeProfile) -> Dict:
        """
        Get a summary dictionary of the profile

        Args:
            profile: VolumeProfile object

        Returns:
            Dictionary with profile summary
        """
        return {
            'vwap': profile.vwap,
            'poc': profile.poc,
            'vah': profile.vah,
            'val': profile.val,
            'value_area_range': profile.vah - profile.val,
            'value_area_percentage': (profile.value_area_volume / profile.total_volume) * 100,
            'total_volume': profile.total_volume,
            'price_levels_count': len(profile.price_levels)
        }
