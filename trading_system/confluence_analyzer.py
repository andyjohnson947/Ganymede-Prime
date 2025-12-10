"""
Real-Time Confluence Analyzer
Detects high-value trade setups based on EA reverse engineering
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import trading_config as config


class ConfluenceAnalyzer:
    """Analyzes market conditions for confluence-based entry signals"""

    def __init__(self):
        self.previous_day_levels = {}
        self.current_vwap = None
        self.current_vwap_std = None

    def calculate_previous_day_levels(self, historical_data: pd.DataFrame) -> Dict:
        """
        Calculate previous trading day's institutional levels

        Returns dict with: POC, VAH, VAL, VWAP, LVN
        """
        if historical_data.empty or len(historical_data) < 10:
            return {}

        # Get yesterday's date
        today = datetime.now().date()
        prev_date = today - timedelta(days=1)

        # Handle weekends - look back up to 5 days
        for _ in range(config.PREV_DAY_LOOKBACK_DAYS):
            prev_day_data = historical_data[
                historical_data.index.date == prev_date
            ]

            if not prev_day_data.empty and len(prev_day_data) > 10:
                break
            prev_date = prev_date - timedelta(days=1)

        if prev_day_data.empty:
            return {}

        levels = {}

        # Previous day VWAP
        if 'VWAP' in prev_day_data.columns:
            levels['vwap'] = prev_day_data['VWAP'].iloc[-1]

        # Calculate Volume Profile for previous day
        price_min = prev_day_data['low'].min()
        price_max = prev_day_data['high'].max()
        price_range = price_max - price_min

        if price_range > 0:
            num_bins = config.VP_NUM_BINS
            bin_size = price_range / num_bins
            volume_at_price = {}

            # Distribute volume across price bins
            for _, candle in prev_day_data.iterrows():
                low_bin = int((candle['low'] - price_min) / bin_size)
                high_bin = int((candle['high'] - price_min) / bin_size)
                bins_covered = max(1, high_bin - low_bin + 1)
                volume_per_bin = candle.get('tick_volume', 0) / bins_covered

                for bin_idx in range(low_bin, high_bin + 1):
                    if 0 <= bin_idx < num_bins:
                        volume_at_price[bin_idx] = volume_at_price.get(bin_idx, 0) + volume_per_bin

            if volume_at_price:
                # POC (Point of Control - highest volume)
                poc_bin = max(volume_at_price, key=volume_at_price.get)
                levels['poc'] = price_min + (poc_bin * bin_size) + (bin_size / 2)

                # VAH and VAL (70% value area)
                total_volume = sum(volume_at_price.values())
                target_volume = total_volume * config.VP_VALUE_AREA_PCT

                sorted_bins = sorted(volume_at_price.items(),
                                   key=lambda x: x[1], reverse=True)

                accumulated_volume = 0
                value_area_bins = []

                for bin_idx, vol in sorted_bins:
                    value_area_bins.append(bin_idx)
                    accumulated_volume += vol
                    if accumulated_volume >= target_volume:
                        break

                if value_area_bins:
                    levels['vah'] = price_min + (max(value_area_bins) * bin_size) + bin_size
                    levels['val'] = price_min + (min(value_area_bins) * bin_size)

                # LVN (Low Volume Node - lowest volume)
                lvn_bin = min(volume_at_price, key=volume_at_price.get)
                levels['lvn'] = price_min + (lvn_bin * bin_size) + (bin_size / 2)

        self.previous_day_levels = levels
        return levels

    def calculate_vwap_bands(self, current_data: pd.DataFrame) -> Dict:
        """Calculate VWAP and deviation bands"""
        if current_data.empty or 'VWAP' not in current_data.columns:
            return {}

        recent_data = current_data.tail(config.VP_LOOKBACK_BARS)

        if len(recent_data) < 20:
            return {}

        # Get current VWAP
        vwap = current_data['VWAP'].iloc[-1]

        # Calculate standard deviation
        vwap_std = recent_data['close'].std()

        bands = {
            'vwap': vwap,
            'std': vwap_std,
            'band_1_upper': vwap + (vwap_std * config.VWAP_BAND_1_STDDEV),
            'band_1_lower': vwap - (vwap_std * config.VWAP_BAND_1_STDDEV),
            'band_2_upper': vwap + (vwap_std * config.VWAP_BAND_2_STDDEV),
            'band_2_lower': vwap - (vwap_std * config.VWAP_BAND_2_STDDEV),
            'band_3_upper': vwap + (vwap_std * config.VWAP_BAND_3_STDDEV),
            'band_3_lower': vwap - (vwap_std * config.VWAP_BAND_3_STDDEV),
        }

        self.current_vwap = vwap
        self.current_vwap_std = vwap_std

        return bands

    def detect_swing_levels(self, current_data: pd.DataFrame) -> Dict:
        """Detect swing highs and lows"""
        if current_data.empty or len(current_data) < config.SWING_LOOKBACK_BARS:
            return {}

        lookback = current_data.tail(config.SWING_LOOKBACK_BARS)

        return {
            'swing_high': lookback['high'].max(),
            'swing_low': lookback['low'].min(),
        }

    def calculate_volume_profile(self, current_data: pd.DataFrame) -> Dict:
        """Calculate current volume profile (POC, VAH, VAL)"""
        if current_data.empty or len(current_data) < 50:
            return {}

        lookback = current_data.tail(config.VP_LOOKBACK_BARS)

        price_min = lookback['low'].min()
        price_max = lookback['high'].max()
        price_range = price_max - price_min

        if price_range == 0:
            return {}

        num_bins = config.VP_NUM_BINS
        bin_size = price_range / num_bins
        volume_at_price = {}

        for _, candle in lookback.iterrows():
            low_bin = int((candle['low'] - price_min) / bin_size)
            high_bin = int((candle['high'] - price_min) / bin_size)
            bins_covered = max(1, high_bin - low_bin + 1)
            volume_per_bin = candle.get('tick_volume', 0) / bins_covered

            for bin_idx in range(low_bin, high_bin + 1):
                if 0 <= bin_idx < num_bins:
                    volume_at_price[bin_idx] = volume_at_price.get(bin_idx, 0) + volume_per_bin

        if not volume_at_price:
            return {}

        # POC
        poc_bin = max(volume_at_price, key=volume_at_price.get)
        poc = price_min + (poc_bin * bin_size) + (bin_size / 2)

        # VAH and VAL
        total_volume = sum(volume_at_price.values())
        target_volume = total_volume * config.VP_VALUE_AREA_PCT

        sorted_bins = sorted(volume_at_price.items(),
                           key=lambda x: x[1], reverse=True)

        accumulated_volume = 0
        value_area_bins = []

        for bin_idx, vol in sorted_bins:
            value_area_bins.append(bin_idx)
            accumulated_volume += vol
            if accumulated_volume >= target_volume:
                break

        vah = price_min + (max(value_area_bins) * bin_size) + bin_size if value_area_bins else None
        val = price_min + (min(value_area_bins) * bin_size) if value_area_bins else None

        # LVN
        lvn_bin = min(volume_at_price, key=volume_at_price.get)
        lvn = price_min + (lvn_bin * bin_size) + (bin_size / 2)

        return {
            'poc': poc,
            'vah': vah,
            'val': val,
            'lvn': lvn,
        }

    def check_trend_filter(self, current_data: pd.DataFrame) -> bool:
        """
        Check if market is ranging (not trending)
        Returns True if safe to trade (ranging market)
        """
        if current_data.empty or len(current_data) < config.TREND_LOOKBACK_BARS:
            return False

        lookback = current_data.tail(config.TREND_LOOKBACK_BARS)

        # Calculate trend strength (price change percentage)
        price_change_pct = abs(
            (lookback['close'].iloc[-1] - lookback['close'].iloc[0]) /
            lookback['close'].iloc[0] * 100
        )

        # Market is ranging if trend < 1%
        is_ranging = price_change_pct < config.MAX_TREND_STRENGTH_PCT

        return is_ranging

    def analyze_confluence(self, current_price: float, current_data: pd.DataFrame) -> Dict:
        """
        Main confluence analysis - checks all factors

        Returns:
            {
                'should_trade': bool,
                'direction': 'buy' or 'sell',
                'confluence_score': int,
                'factors': List[str],
                'confidence': float,
            }
        """
        confluence_score = 0
        factors = []
        direction = None

        # Check trending market filter
        if not self.check_trend_filter(current_data):
            return {
                'should_trade': False,
                'reason': 'Trending market detected - EA only trades ranging markets',
                'confluence_score': 0,
                'factors': [],
            }

        # Calculate all levels
        vwap_bands = self.calculate_vwap_bands(current_data)
        swing_levels = self.detect_swing_levels(current_data)
        volume_profile = self.calculate_volume_profile(current_data)

        if not self.previous_day_levels:
            self.calculate_previous_day_levels(current_data)

        tolerance = current_price * config.CONFLUENCE_TOLERANCE_PCT

        # Check VWAP bands (PRIMARY SIGNAL)
        if vwap_bands:
            vwap = vwap_bands['vwap']

            # Band 1
            if (vwap_bands['band_1_lower'] <= current_price <= vwap_bands['band_1_upper']):
                confluence_score += 1
                factors.append('VWAP Band 1')

                # Determine direction based on VWAP
                if current_price < vwap:
                    direction = 'buy'  # Below VWAP = oversold
                else:
                    direction = 'sell'  # Above VWAP = overbought

            # Band 2
            elif (vwap_bands['band_2_lower'] <= current_price <= vwap_bands['band_2_upper']):
                confluence_score += 1
                factors.append('VWAP Band 2')

                if current_price < vwap:
                    direction = 'buy'
                else:
                    direction = 'sell'

        # Check previous day levels (CRITICAL)
        for level_name, level_price in self.previous_day_levels.items():
            if level_price and abs(current_price - level_price) < tolerance:
                confluence_score += 1
                factors.append(f'Prev Day {level_name.upper()}')

        # Check current volume profile
        if volume_profile:
            if volume_profile.get('poc') and abs(current_price - volume_profile['poc']) < tolerance:
                confluence_score += 1
                factors.append('POC')

            if volume_profile.get('vah') and current_price > volume_profile['vah']:
                confluence_score += 1
                factors.append('Above VAH')

            if volume_profile.get('val') and current_price < volume_profile['val']:
                confluence_score += 1
                factors.append('Below VAL')

            if volume_profile.get('lvn') and abs(current_price - volume_profile['lvn']) < tolerance:
                confluence_score += 1
                factors.append('LVN')

        # Check swing levels
        if swing_levels:
            if swing_levels.get('swing_high') and abs(current_price - swing_levels['swing_high']) < tolerance:
                confluence_score += 1
                factors.append('Swing High')

            if swing_levels.get('swing_low') and abs(current_price - swing_levels['swing_low']) < tolerance:
                confluence_score += 1
                factors.append('Swing Low')

        # Decision logic
        should_trade = (
            confluence_score >= config.MIN_CONFLUENCE_SCORE and
            direction is not None
        )

        # Calculate confidence (0-1 scale)
        confidence = min(confluence_score / 8.0, 1.0)  # Max 8 factors

        return {
            'should_trade': should_trade,
            'direction': direction,
            'confluence_score': confluence_score,
            'factors': factors,
            'confidence': confidence,
            'vwap': vwap_bands.get('vwap') if vwap_bands else None,
        }
