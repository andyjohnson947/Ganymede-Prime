"""
Multi-Timeframe Analysis Module
Analyzes LVN levels, session volatility, weekly institutional levels,
recovery patterns, and time-based correlations
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging


class MultiTimeframeAnalyzer:
    """
    Comprehensive multi-timeframe analysis for trading strategies
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.sessions = {
            'Tokyo': {'start': 0, 'end': 9},      # 00:00-09:00 UTC
            'London': {'start': 8, 'end': 17},     # 08:00-17:00 UTC
            'New York': {'start': 13, 'end': 22},  # 13:00-22:00 UTC
            'Sydney': {'start': 22, 'end': 7}      # 22:00-07:00 UTC (wraps)
        }

    def calculate_lvn_multi_timeframe(
        self,
        market_data: pd.DataFrame,
        timeframes: List[str] = ['H1', 'D1', 'W1']
    ) -> Dict:
        """
        Calculate Low Volume Nodes across multiple timeframes

        Args:
            market_data: DataFrame with OHLCV data (hourly)
            timeframes: List of timeframes to analyze

        Returns:
            Dict with LVN levels for each timeframe
        """
        lvn_levels = {}

        try:
            # Hourly LVN (last 100 bars)
            if 'H1' in timeframes:
                h1_data = market_data.tail(100)
                lvn_levels['H1'] = self._calculate_volume_profile_lvn(
                    h1_data, 'Hourly (100 bars)'
                )

            # Daily LVN (last 20 days)
            if 'D1' in timeframes:
                daily_data = market_data.resample('D').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'tick_volume': 'sum'
                }).dropna().tail(20)
                lvn_levels['D1'] = self._calculate_volume_profile_lvn(
                    daily_data, 'Daily (20 days)'
                )

            # Weekly LVN (last 12 weeks)
            if 'W1' in timeframes:
                weekly_data = market_data.resample('W').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'tick_volume': 'sum'
                }).dropna().tail(12)
                lvn_levels['W1'] = self._calculate_volume_profile_lvn(
                    weekly_data, 'Weekly (12 weeks)'
                )

            self.logger.info(f"Calculated LVN levels for {len(lvn_levels)} timeframes")

        except Exception as e:
            self.logger.error(f"Error calculating multi-timeframe LVN: {e}")

        return lvn_levels

    def _calculate_volume_profile_lvn(
        self,
        data: pd.DataFrame,
        label: str
    ) -> Dict:
        """
        Calculate volume profile and identify Low Volume Nodes

        Returns:
            Dict with POC, VAH, VAL, and LVN levels
        """
        if data.empty or len(data) < 10:
            return {}

        try:
            price_min = data['low'].min()
            price_max = data['high'].max()
            price_range = price_max - price_min

            if price_range == 0:
                return {}

            # Create volume profile (50 price bins)
            num_bins = 50
            bin_size = price_range / num_bins
            volume_at_price = {}

            for _, candle in data.iterrows():
                low_bin = int((candle['low'] - price_min) / bin_size)
                high_bin = int((candle['high'] - price_min) / bin_size)
                bins_covered = max(1, high_bin - low_bin + 1)
                volume_per_bin = candle.get('tick_volume', 0) / bins_covered

                for bin_idx in range(low_bin, min(high_bin + 1, num_bins)):
                    if 0 <= bin_idx < num_bins:
                        volume_at_price[bin_idx] = volume_at_price.get(bin_idx, 0) + volume_per_bin

            if not volume_at_price:
                return {}

            # POC (Point of Control - highest volume)
            poc_bin = max(volume_at_price, key=volume_at_price.get)
            poc = price_min + (poc_bin * bin_size) + (bin_size / 2)

            # VAH and VAL (70% value area)
            total_volume = sum(volume_at_price.values())
            target_volume = total_volume * 0.70

            sorted_bins = sorted(volume_at_price.items(), key=lambda x: x[1], reverse=True)
            accumulated_volume = 0
            value_area_bins = []

            for bin_idx, vol in sorted_bins:
                value_area_bins.append(bin_idx)
                accumulated_volume += vol
                if accumulated_volume >= target_volume:
                    break

            vah = price_min + (max(value_area_bins) * bin_size) + bin_size if value_area_bins else None
            val = price_min + (min(value_area_bins) * bin_size) if value_area_bins else None

            # LVN (Low Volume Nodes) - identify top 5 lowest volume areas
            lvn_bins = sorted(volume_at_price.items(), key=lambda x: x[1])[:5]
            lvn_levels = [
                price_min + (bin_idx * bin_size) + (bin_size / 2)
                for bin_idx, _ in lvn_bins
            ]

            # HVN (High Volume Nodes) - identify top 5 highest volume areas
            hvn_bins = sorted(volume_at_price.items(), key=lambda x: x[1], reverse=True)[:5]
            hvn_levels = [
                price_min + (bin_idx * bin_size) + (bin_size / 2)
                for bin_idx, _ in hvn_bins
            ]

            # Volume-weighted standard deviation
            prices = []
            volumes = []
            for bin_idx, vol in volume_at_price.items():
                price = price_min + (bin_idx * bin_size) + (bin_size / 2)
                prices.append(price)
                volumes.append(vol)

            weighted_mean = sum(p * v for p, v in zip(prices, volumes)) / sum(volumes)
            weighted_variance = sum(v * (p - weighted_mean) ** 2 for p, v in zip(prices, volumes)) / sum(volumes)
            weighted_std = weighted_variance ** 0.5

            return {
                'label': label,
                'poc': poc,
                'vah': vah,
                'val': val,
                'lvn_levels': lvn_levels,
                'hvn_levels': hvn_levels,
                'volume_weighted_std': weighted_std,
                'total_volume': total_volume
            }

        except Exception as e:
            self.logger.error(f"Error in volume profile calculation: {e}")
            return {}

    def calculate_session_volatility_atr(
        self,
        market_data: pd.DataFrame,
        atr_period: int = 14
    ) -> Dict:
        """
        Correlate entry success with ATR by trading session

        Args:
            market_data: DataFrame with OHLCV data
            atr_period: ATR calculation period

        Returns:
            Dict with ATR statistics per session
        """
        session_stats = {}

        try:
            # Calculate ATR
            data = market_data.copy()
            data['high_low'] = data['high'] - data['low']
            data['high_close'] = abs(data['high'] - data['close'].shift(1))
            data['low_close'] = abs(data['low'] - data['close'].shift(1))
            data['true_range'] = data[['high_low', 'high_close', 'low_close']].max(axis=1)
            data['ATR'] = data['true_range'].rolling(window=atr_period).mean()

            # Analyze each session
            data['hour'] = data.index.hour

            for session_name, session_hours in self.sessions.items():
                if session_name == 'Sydney':
                    # Handle wrap-around for Sydney session
                    session_data = data[
                        (data['hour'] >= session_hours['start']) |
                        (data['hour'] < session_hours['end'])
                    ]
                else:
                    session_data = data[
                        (data['hour'] >= session_hours['start']) &
                        (data['hour'] < session_hours['end'])
                    ]

                if not session_data.empty and 'ATR' in session_data.columns:
                    atr_values = session_data['ATR'].dropna()

                    if len(atr_values) > 0:
                        session_stats[session_name] = {
                            'avg_atr': float(atr_values.mean()),
                            'min_atr': float(atr_values.min()),
                            'max_atr': float(atr_values.max()),
                            'std_atr': float(atr_values.std()),
                            'median_atr': float(atr_values.median()),
                            'sample_size': len(atr_values),
                            'volatility_rank': None  # Will set after comparing all
                        }

            # Rank sessions by volatility
            if session_stats:
                sorted_sessions = sorted(
                    session_stats.items(),
                    key=lambda x: x[1]['avg_atr'],
                    reverse=True
                )
                for rank, (session, stats) in enumerate(sorted_sessions, 1):
                    session_stats[session]['volatility_rank'] = rank

            self.logger.info(f"Calculated ATR for {len(session_stats)} sessions")

        except Exception as e:
            self.logger.error(f"Error calculating session volatility: {e}")

        return session_stats

    def calculate_previous_week_levels(
        self,
        market_data: pd.DataFrame
    ) -> Dict:
        """
        Calculate previous week's institutional levels (VWAP, POC, VAH, VAL, LVN, HVN)

        Args:
            market_data: DataFrame with OHLCV data

        Returns:
            Dict with previous week's levels
        """
        try:
            # Get last complete week's data
            today = datetime.now().date()
            days_since_monday = today.weekday()
            last_monday = today - timedelta(days=days_since_monday + 7)
            last_sunday = last_monday + timedelta(days=6)

            # Filter data for previous week
            prev_week_data = market_data[
                (market_data.index.date >= last_monday) &
                (market_data.index.date <= last_sunday)
            ]

            if prev_week_data.empty or len(prev_week_data) < 10:
                self.logger.warning("Insufficient data for previous week analysis")
                return {}

            # Calculate VWAP for previous week
            typical_price = (
                prev_week_data['high'] +
                prev_week_data['low'] +
                prev_week_data['close']
            ) / 3
            vwap = (
                (typical_price * prev_week_data['tick_volume']).sum() /
                prev_week_data['tick_volume'].sum()
            )

            # Calculate VWAP standard deviation bands
            vwap_std = prev_week_data['close'].std()
            vwap_bands = {
                'vwap': float(vwap),
                'upper_1std': float(vwap + vwap_std * 1),
                'lower_1std': float(vwap - vwap_std * 1),
                'upper_2std': float(vwap + vwap_std * 2),
                'lower_2std': float(vwap - vwap_std * 2),
                'upper_3std': float(vwap + vwap_std * 3),
                'lower_3std': float(vwap - vwap_std * 3),
            }

            # Calculate volume profile
            volume_profile = self._calculate_volume_profile_lvn(
                prev_week_data,
                f"Previous Week ({last_monday} to {last_sunday})"
            )

            # Calculate swing levels for the week
            swing_highs = self._find_swing_points(prev_week_data, point_type='high')
            swing_lows = self._find_swing_points(prev_week_data, point_type='low')

            # Calculate initial balance (first 2 hours of Monday)
            monday_data = prev_week_data[prev_week_data.index.date == last_monday]
            if len(monday_data) >= 2:
                initial_balance = {
                    'high': float(monday_data.head(2)['high'].max()),
                    'low': float(monday_data.head(2)['low'].min()),
                    'range': float(monday_data.head(2)['high'].max() - monday_data.head(2)['low'].min())
                }
            else:
                initial_balance = {}

            levels = {
                'week_start': last_monday,
                'week_end': last_sunday,
                'open': float(prev_week_data.iloc[0]['open']),
                'high': float(prev_week_data['high'].max()),
                'low': float(prev_week_data['low'].min()),
                'close': float(prev_week_data.iloc[-1]['close']),
                'range': float(prev_week_data['high'].max() - prev_week_data['low'].min()),
                'vwap_bands': vwap_bands,
                'volume_profile': volume_profile,
                'swing_highs': swing_highs,
                'swing_lows': swing_lows,
                'initial_balance': initial_balance,
                'midpoint': float((prev_week_data['high'].max() + prev_week_data['low'].min()) / 2)
            }

            self.logger.info(f"Calculated previous week levels: {last_monday} to {last_sunday}")

            return levels

        except Exception as e:
            self.logger.error(f"Error calculating previous week levels: {e}")
            return {}

    def _find_swing_points(
        self,
        data: pd.DataFrame,
        point_type: str = 'high',
        lookback: int = 5
    ) -> List[float]:
        """
        Find swing high/low points in the data

        Args:
            data: DataFrame with OHLCV data
            point_type: 'high' or 'low'
            lookback: Number of bars to look back/forward

        Returns:
            List of swing point prices
        """
        swing_points = []

        try:
            price_series = data[point_type]

            for i in range(lookback, len(price_series) - lookback):
                current_price = price_series.iloc[i]
                window_before = price_series.iloc[i - lookback:i]
                window_after = price_series.iloc[i + 1:i + lookback + 1]

                if point_type == 'high':
                    # Swing high: higher than surrounding bars
                    if current_price >= window_before.max() and current_price >= window_after.max():
                        swing_points.append(float(current_price))
                else:
                    # Swing low: lower than surrounding bars
                    if current_price <= window_before.min() and current_price <= window_after.min():
                        swing_points.append(float(current_price))

            # Return top 5 most significant swing points
            if point_type == 'high':
                swing_points = sorted(swing_points, reverse=True)[:5]
            else:
                swing_points = sorted(swing_points)[:5]

        except Exception as e:
            self.logger.error(f"Error finding swing points: {e}")

        return swing_points

    def calculate_recovery_success_rate(
        self,
        trades_df: pd.DataFrame,
        recovery_patterns: List[Dict]
    ) -> Dict:
        """
        Track which recovery sequences win/lose

        Args:
            trades_df: DataFrame with all trades
            recovery_patterns: List of detected recovery/DCA patterns

        Returns:
            Dict with success rate statistics per recovery level
        """
        recovery_stats = {
            'total_sequences': len(recovery_patterns),
            'by_level': {},
            'by_sequence_length': {},
            'overall_success_rate': 0.0
        }

        try:
            successful_sequences = 0
            failed_sequences = 0

            for pattern in recovery_patterns:
                trades = pattern.get('trades', [])
                if not trades:
                    continue

                # Calculate sequence outcome
                total_profit = sum(t.get('profit', 0) for t in trades)
                sequence_length = len(trades)

                is_successful = total_profit > 0

                if is_successful:
                    successful_sequences += 1
                else:
                    failed_sequences += 1

                # Track by sequence length
                if sequence_length not in recovery_stats['by_sequence_length']:
                    recovery_stats['by_sequence_length'][sequence_length] = {
                        'total': 0,
                        'successful': 0,
                        'failed': 0,
                        'avg_profit': 0.0,
                        'total_profit': 0.0
                    }

                stats = recovery_stats['by_sequence_length'][sequence_length]
                stats['total'] += 1
                if is_successful:
                    stats['successful'] += 1
                else:
                    stats['failed'] += 1
                stats['total_profit'] += total_profit

                # Track individual trade levels
                for level, trade in enumerate(trades, 1):
                    if level not in recovery_stats['by_level']:
                        recovery_stats['by_level'][level] = {
                            'count': 0,
                            'avg_volume': 0.0,
                            'total_volume': 0.0,
                            'avg_profit': 0.0,
                            'total_profit': 0.0
                        }

                    level_stats = recovery_stats['by_level'][level]
                    level_stats['count'] += 1
                    level_stats['total_volume'] += trade.get('volume', 0)
                    level_stats['total_profit'] += trade.get('profit', 0)

            # Calculate averages
            for length, stats in recovery_stats['by_sequence_length'].items():
                if stats['total'] > 0:
                    stats['success_rate'] = (stats['successful'] / stats['total']) * 100
                    stats['avg_profit'] = stats['total_profit'] / stats['total']

            for level, stats in recovery_stats['by_level'].items():
                if stats['count'] > 0:
                    stats['avg_volume'] = stats['total_volume'] / stats['count']
                    stats['avg_profit'] = stats['total_profit'] / stats['count']

            # Overall success rate
            total = successful_sequences + failed_sequences
            if total > 0:
                recovery_stats['overall_success_rate'] = (successful_sequences / total) * 100

            recovery_stats['successful_sequences'] = successful_sequences
            recovery_stats['failed_sequences'] = failed_sequences

            self.logger.info(
                f"Recovery analysis: {successful_sequences} successful, "
                f"{failed_sequences} failed ({recovery_stats['overall_success_rate']:.1f}% success rate)"
            )

        except Exception as e:
            self.logger.error(f"Error calculating recovery success rate: {e}")

        return recovery_stats

    def analyze_time_based_patterns(
        self,
        trades_df: pd.DataFrame,
        market_data: pd.DataFrame
    ) -> Dict:
        """
        Correlate entry success with time of day and day of week

        Args:
            trades_df: DataFrame with all trades
            market_data: DataFrame with market data

        Returns:
            Dict with time-based correlation statistics
        """
        time_stats = {
            'by_hour': {},
            'by_day_of_week': {},
            'by_session': {},
            'best_times': []
        }

        try:
            # Ensure we have entry time
            if 'entry_time' not in trades_df.columns:
                return time_stats

            trades = trades_df.copy()
            trades['entry_time'] = pd.to_datetime(trades['entry_time'])
            trades['hour'] = trades['entry_time'].dt.hour
            trades['day_of_week'] = trades['entry_time'].dt.day_name()
            trades['is_profitable'] = trades.get('profit', 0) > 0

            # Closed trades only for accuracy
            closed_trades = trades[trades.get('exit_time').notna()]

            if closed_trades.empty:
                return time_stats

            # Analysis by hour
            for hour in range(24):
                hour_trades = closed_trades[closed_trades['hour'] == hour]

                if not hour_trades.empty:
                    time_stats['by_hour'][hour] = {
                        'total_trades': len(hour_trades),
                        'winning_trades': int(hour_trades['is_profitable'].sum()),
                        'win_rate': float((hour_trades['is_profitable'].sum() / len(hour_trades)) * 100),
                        'avg_profit': float(hour_trades.get('profit', 0).mean()),
                        'total_profit': float(hour_trades.get('profit', 0).sum())
                    }

            # Analysis by day of week
            for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
                day_trades = closed_trades[closed_trades['day_of_week'] == day]

                if not day_trades.empty:
                    time_stats['by_day_of_week'][day] = {
                        'total_trades': len(day_trades),
                        'winning_trades': int(day_trades['is_profitable'].sum()),
                        'win_rate': float((day_trades['is_profitable'].sum() / len(day_trades)) * 100),
                        'avg_profit': float(day_trades.get('profit', 0).mean()),
                        'total_profit': float(day_trades.get('profit', 0).sum())
                    }

            # Analysis by session
            for session_name, session_hours in self.sessions.items():
                if session_name == 'Sydney':
                    session_trades = closed_trades[
                        (closed_trades['hour'] >= session_hours['start']) |
                        (closed_trades['hour'] < session_hours['end'])
                    ]
                else:
                    session_trades = closed_trades[
                        (closed_trades['hour'] >= session_hours['start']) &
                        (closed_trades['hour'] < session_hours['end'])
                    ]

                if not session_trades.empty:
                    time_stats['by_session'][session_name] = {
                        'total_trades': len(session_trades),
                        'winning_trades': int(session_trades['is_profitable'].sum()),
                        'win_rate': float((session_trades['is_profitable'].sum() / len(session_trades)) * 100),
                        'avg_profit': float(session_trades.get('profit', 0).mean()),
                        'total_profit': float(session_trades.get('profit', 0).sum())
                    }

            # Identify best times (top 5 hours by win rate with min 3 trades)
            qualified_hours = {
                hour: stats for hour, stats in time_stats['by_hour'].items()
                if stats['total_trades'] >= 3
            }

            if qualified_hours:
                sorted_hours = sorted(
                    qualified_hours.items(),
                    key=lambda x: (x[1]['win_rate'], x[1]['total_trades']),
                    reverse=True
                )[:5]

                time_stats['best_times'] = [
                    {
                        'hour': hour,
                        'win_rate': stats['win_rate'],
                        'total_trades': stats['total_trades'],
                        'avg_profit': stats['avg_profit']
                    }
                    for hour, stats in sorted_hours
                ]

            self.logger.info(f"Analyzed time-based patterns for {len(closed_trades)} closed trades")

        except Exception as e:
            self.logger.error(f"Error analyzing time-based patterns: {e}")

        return time_stats

    def generate_comprehensive_report(
        self,
        market_data: pd.DataFrame,
        trades_df: pd.DataFrame,
        recovery_patterns: List[Dict] = None
    ) -> Dict:
        """
        Generate complete multi-timeframe analysis report

        Args:
            market_data: DataFrame with OHLCV data
            trades_df: DataFrame with all trades
            recovery_patterns: Optional list of recovery patterns

        Returns:
            Dict with all analysis results
        """
        self.logger.info("Starting comprehensive multi-timeframe analysis...")

        report = {
            'analysis_timestamp': datetime.now().isoformat(),
            'lvn_multi_timeframe': {},
            'session_volatility': {},
            'previous_week_levels': {},
            'recovery_success_rate': {},
            'time_based_patterns': {}
        }

        try:
            # 1. LVN Multi-Timeframe Analysis
            self.logger.info("Calculating multi-timeframe LVN levels...")
            report['lvn_multi_timeframe'] = self.calculate_lvn_multi_timeframe(
                market_data,
                timeframes=['H1', 'D1', 'W1']
            )

            # 2. Session Volatility with ATR
            self.logger.info("Analyzing session volatility...")
            report['session_volatility'] = self.calculate_session_volatility_atr(
                market_data,
                atr_period=14
            )

            # 3. Previous Week Levels
            self.logger.info("Calculating previous week institutional levels...")
            report['previous_week_levels'] = self.calculate_previous_week_levels(
                market_data
            )

            # 4. Recovery Success Rate (if patterns provided)
            if recovery_patterns:
                self.logger.info("Analyzing recovery success rates...")
                report['recovery_success_rate'] = self.calculate_recovery_success_rate(
                    trades_df,
                    recovery_patterns
                )

            # 5. Time-Based Patterns
            if not trades_df.empty:
                self.logger.info("Analyzing time-based patterns...")
                report['time_based_patterns'] = self.analyze_time_based_patterns(
                    trades_df,
                    market_data
                )

            self.logger.info("Multi-timeframe analysis complete!")

        except Exception as e:
            self.logger.error(f"Error generating comprehensive report: {e}")

        return report

    def print_analysis_summary(self, report: Dict):
        """Print formatted summary of analysis results"""

        print("\n" + "=" * 80)
        print("MULTI-TIMEFRAME ANALYSIS REPORT")
        print("=" * 80)

        # LVN Multi-Timeframe
        if report.get('lvn_multi_timeframe'):
            print("\n📊 VOLUME PROFILE ANALYSIS - MULTI-TIMEFRAME")
            print("-" * 80)

            for tf, levels in report['lvn_multi_timeframe'].items():
                if levels and 'label' in levels:
                    print(f"\n{tf} - {levels['label']}:")
                    print(f"  POC (Point of Control): {levels.get('poc', 0):.5f}")
                    print(f"  VAH (Value Area High):  {levels.get('vah', 0):.5f}")
                    print(f"  VAL (Value Area Low):   {levels.get('val', 0):.5f}")
                    print(f"  Volume Weighted StdDev: {levels.get('volume_weighted_std', 0):.5f}")
                    print(f"  \n  📉 LVN Levels (Low Volume - Breakout Zones):")
                    for i, lvn in enumerate(levels.get('lvn_levels', []), 1):
                        print(f"     {i}. {lvn:.5f}")
                    print(f"  \n  📈 HVN Levels (High Volume - Support/Resistance):")
                    for i, hvn in enumerate(levels.get('hvn_levels', []), 1):
                        print(f"     {i}. {hvn:.5f}")
                    print(f"  \n  Total Volume: {levels.get('total_volume', 0):,.0f}")

        # Session Volatility
        if report.get('session_volatility'):
            print("\n📈 SESSION VOLATILITY (ATR)")
            print("-" * 80)

            for session, stats in sorted(
                report['session_volatility'].items(),
                key=lambda x: x[1]['avg_atr'],
                reverse=True
            ):
                print(f"\n{session} (Rank #{stats['volatility_rank']}):")
                print(f"  Avg ATR: {stats['avg_atr']:.5f}")
                print(f"  Min/Max: {stats['min_atr']:.5f} / {stats['max_atr']:.5f}")
                print(f"  Std Dev: {stats['std_atr']:.5f}")
                print(f"  Sample Size: {stats['sample_size']} bars")

        # Previous Week Levels
        if report.get('previous_week_levels'):
            levels = report['previous_week_levels']
            print("\n📅 PREVIOUS WEEK INSTITUTIONAL LEVELS")
            print("-" * 80)
            print(f"Week: {levels.get('week_start')} to {levels.get('week_end')}")
            print(f"\nKey Price Levels:")
            print(f"  Open:     {levels.get('open', 0):.5f}")
            print(f"  High:     {levels.get('high', 0):.5f}")
            print(f"  Low:      {levels.get('low', 0):.5f}")
            print(f"  Close:    {levels.get('close', 0):.5f}")
            print(f"  Midpoint: {levels.get('midpoint', 0):.5f}")
            print(f"  Range:    {levels.get('range', 0):.5f}")

            if 'vwap_bands' in levels and levels['vwap_bands']:
                vwap = levels['vwap_bands']
                print(f"\nVWAP & Deviation Bands:")
                print(f"  VWAP:         {vwap.get('vwap', 0):.5f}")
                print(f"  Upper 3σ:     {vwap.get('upper_3std', 0):.5f}")
                print(f"  Upper 2σ:     {vwap.get('upper_2std', 0):.5f}")
                print(f"  Upper 1σ:     {vwap.get('upper_1std', 0):.5f}")
                print(f"  Lower 1σ:     {vwap.get('lower_1std', 0):.5f}")
                print(f"  Lower 2σ:     {vwap.get('lower_2std', 0):.5f}")
                print(f"  Lower 3σ:     {vwap.get('lower_3std', 0):.5f}")

            if 'volume_profile' in levels and levels['volume_profile']:
                vp = levels['volume_profile']
                print(f"\nVolume Profile:")
                print(f"  POC: {vp.get('poc', 0):.5f}")
                print(f"  VAH: {vp.get('vah', 0):.5f}")
                print(f"  VAL: {vp.get('val', 0):.5f}")

                if 'hvn_levels' in vp and vp['hvn_levels']:
                    print(f"  HVN Levels: {', '.join([f'{h:.5f}' for h in vp['hvn_levels'][:3]])}")
                if 'lvn_levels' in vp and vp['lvn_levels']:
                    print(f"  LVN Levels: {', '.join([f'{l:.5f}' for l in vp['lvn_levels'][:3]])}")

            if 'swing_highs' in levels and levels['swing_highs']:
                print(f"\nSwing Highs: {', '.join([f'{s:.5f}' for s in levels['swing_highs']])}")

            if 'swing_lows' in levels and levels['swing_lows']:
                print(f"Swing Lows:  {', '.join([f'{s:.5f}' for s in levels['swing_lows']])}")

            if 'initial_balance' in levels and levels['initial_balance']:
                ib = levels['initial_balance']
                print(f"\nInitial Balance (Monday First 2H):")
                print(f"  High:  {ib.get('high', 0):.5f}")
                print(f"  Low:   {ib.get('low', 0):.5f}")
                print(f"  Range: {ib.get('range', 0):.5f}")

        # Recovery Success Rate
        if report.get('recovery_success_rate'):
            stats = report['recovery_success_rate']
            print("\n💰 RECOVERY SEQUENCE SUCCESS RATE")
            print("-" * 80)
            print(f"Total Sequences: {stats.get('total_sequences', 0)}")
            print(f"Successful: {stats.get('successful_sequences', 0)}")
            print(f"Failed: {stats.get('failed_sequences', 0)}")
            print(f"Overall Success Rate: {stats.get('overall_success_rate', 0):.1f}%")

            if 'by_sequence_length' in stats:
                print("\nBy Sequence Length:")
                for length, length_stats in sorted(stats['by_sequence_length'].items()):
                    print(f"  {length} trades: {length_stats.get('success_rate', 0):.1f}% "
                          f"({length_stats.get('successful', 0)}/{length_stats.get('total', 0)}) "
                          f"Avg P/L: ${length_stats.get('avg_profit', 0):.2f}")

        # Time-Based Patterns
        if report.get('time_based_patterns'):
            patterns = report['time_based_patterns']

            if patterns.get('best_times'):
                print("\n⏰ BEST TRADING TIMES")
                print("-" * 80)
                for idx, time_info in enumerate(patterns['best_times'], 1):
                    print(f"{idx}. Hour {time_info['hour']:02d}:00 - "
                          f"Win Rate: {time_info['win_rate']:.1f}% "
                          f"({time_info['total_trades']} trades, "
                          f"Avg P/L: ${time_info['avg_profit']:.2f})")

            if patterns.get('by_session'):
                print("\nBy Trading Session:")
                for session, sess_stats in sorted(
                    patterns['by_session'].items(),
                    key=lambda x: x[1]['win_rate'],
                    reverse=True
                ):
                    print(f"  {session}: {sess_stats['win_rate']:.1f}% "
                          f"({sess_stats['winning_trades']}/{sess_stats['total_trades']}) "
                          f"Avg P/L: ${sess_stats['avg_profit']:.2f}")

        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80 + "\n")
