"""
EA Analyzer
Reverse engineers the EA's strategy by analyzing its trading patterns
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple
from collections import Counter
from scipy import stats

from .ea_monitor import EAMonitor, EATrade


class EAAnalyzer:
    """Analyzes EA behavior to reverse engineer its strategy"""

    def __init__(self, ea_monitor: EAMonitor):
        """
        Initialize EA Analyzer

        Args:
            ea_monitor: EA monitor instance with collected trades
        """
        self.monitor = ea_monitor
        self.logger = logging.getLogger(__name__)

    def analyze_entry_patterns(self) -> Dict:
        """
        Analyze when and why the EA enters trades

        Returns:
            Dictionary with entry pattern analysis
        """
        self.logger.info("Analyzing EA entry patterns...")

        trades_df = self.monitor.get_trades_dataframe()

        if trades_df.empty:
            return {'error': 'No trades to analyze'}

        analysis = {}

        # Time-based patterns
        trades_df['hour'] = pd.to_datetime(trades_df['entry_time']).dt.hour
        trades_df['day_of_week'] = pd.to_datetime(trades_df['entry_time']).dt.dayofweek

        analysis['entry_hours'] = trades_df['hour'].value_counts().to_dict()
        analysis['entry_days'] = trades_df['day_of_week'].value_counts().to_dict()

        # Most active hour
        most_active_hour = trades_df['hour'].mode()[0] if not trades_df['hour'].empty else None
        analysis['most_active_hour'] = int(most_active_hour) if most_active_hour is not None else None

        # Market condition patterns
        condition_cols = [col for col in trades_df.columns if col.startswith('cond_')]

        if condition_cols:
            analysis['market_conditions_at_entry'] = {}

            for col in condition_cols:
                if trades_df[col].notna().any():
                    analysis['market_conditions_at_entry'][col] = {
                        'mean': float(trades_df[col].mean()),
                        'std': float(trades_df[col].std()),
                        'min': float(trades_df[col].min()),
                        'max': float(trades_df[col].max())
                    }

        # Buy vs Sell preference
        type_counts = trades_df['type'].value_counts()
        analysis['trade_direction_preference'] = {
            'buy': int(type_counts.get('buy', 0)),
            'sell': int(type_counts.get('sell', 0)),
            'buy_percentage': float(type_counts.get('buy', 0) / len(trades_df) * 100)
        }

        # Volume patterns
        analysis['volume_stats'] = {
            'mean': float(trades_df['volume'].mean()),
            'std': float(trades_df['volume'].std()),
            'most_common': float(trades_df['volume'].mode()[0]) if not trades_df.empty else 0
        }

        self.logger.info("Entry pattern analysis complete")
        return analysis

    def analyze_exit_patterns(self) -> Dict:
        """
        Analyze how the EA exits trades

        Returns:
            Dictionary with exit pattern analysis
        """
        self.logger.info("Analyzing EA exit patterns...")

        trades_df = self.monitor.get_trades_dataframe()
        closed_trades = trades_df[trades_df['exit_time'].notna()].copy()

        if closed_trades.empty:
            return {'error': 'No closed trades to analyze'}

        analysis = {}

        # Duration analysis
        analysis['duration_stats'] = {
            'mean_hours': float(closed_trades['duration_hours'].mean()),
            'median_hours': float(closed_trades['duration_hours'].median()),
            'min_hours': float(closed_trades['duration_hours'].min()),
            'max_hours': float(closed_trades['duration_hours'].max())
        }

        # Win/loss patterns
        winning = closed_trades[closed_trades['profit'] > 0]
        losing = closed_trades[closed_trades['profit'] < 0]

        analysis['exit_outcomes'] = {
            'total_closed': len(closed_trades),
            'winners': len(winning),
            'losers': len(losing),
            'win_rate': float(len(winning) / len(closed_trades) * 100),
            'avg_win_duration_hours': float(winning['duration_hours'].mean()) if not winning.empty else 0,
            'avg_loss_duration_hours': float(losing['duration_hours'].mean()) if not losing.empty else 0
        }

        # Profit distribution
        analysis['profit_stats'] = {
            'total_profit': float(closed_trades['profit'].sum()),
            'average_win': float(winning['profit'].mean()) if not winning.empty else 0,
            'average_loss': float(losing['profit'].mean()) if not losing.empty else 0,
            'largest_win': float(closed_trades['profit'].max()),
            'largest_loss': float(closed_trades['profit'].min())
        }

        # Pips analysis
        if closed_trades['pips'].notna().any():
            analysis['pips_stats'] = {
                'avg_win_pips': float(winning['pips'].mean()) if not winning.empty else 0,
                'avg_loss_pips': float(losing['pips'].mean()) if not losing.empty else 0
            }

        self.logger.info("Exit pattern analysis complete")
        return analysis

    def detect_strategy_rules(self) -> Dict:
        """
        Attempt to detect the EA's strategy rules

        Returns:
            Dictionary with detected rules
        """
        self.logger.info("Detecting EA strategy rules...")

        trades_df = self.monitor.get_trades_dataframe()

        if trades_df.empty:
            return {'error': 'No trades to analyze'}

        rules = {
            'detected_rules': [],
            'confidence': {}
        }

        # Check for indicator-based rules
        condition_cols = [col for col in trades_df.columns if col.startswith('cond_')]

        for col in condition_cols:
            if trades_df[col].notna().any():
                # Analyze if this indicator correlates with trade type
                buy_trades = trades_df[trades_df['type'] == 'buy']
                sell_trades = trades_df[trades_df['type'] == 'sell']

                if not buy_trades.empty and not sell_trades.empty:
                    buy_mean = buy_trades[col].mean()
                    sell_mean = sell_trades[col].mean()

                    # Statistical test
                    if len(buy_trades) > 1 and len(sell_trades) > 1:
                        t_stat, p_value = stats.ttest_ind(
                            buy_trades[col].dropna(),
                            sell_trades[col].dropna()
                        )

                        if p_value < 0.05:  # Significant difference
                            indicator_name = col.replace('cond_', '')

                            if buy_mean > sell_mean:
                                rule = f"Buys when {indicator_name} is HIGH (avg: {buy_mean:.2f})"
                            else:
                                rule = f"Buys when {indicator_name} is LOW (avg: {buy_mean:.2f})"

                            rules['detected_rules'].append(rule)
                            rules['confidence'][rule] = float(1 - p_value)

        # Check for time-based rules
        if 'hour' in trades_df.columns:
            hour_counts = trades_df['hour'].value_counts()
            if hour_counts.max() / len(trades_df) > 0.3:  # More than 30% in one hour
                peak_hour = hour_counts.idxmax()
                rule = f"Trades mostly during hour {peak_hour}:00"
                rules['detected_rules'].append(rule)
                rules['confidence'][rule] = 0.7

        # Check for volume consistency
        if trades_df['volume'].std() < trades_df['volume'].mean() * 0.1:
            rule = f"Uses fixed lot size: ~{trades_df['volume'].mean():.2f}"
            rules['detected_rules'].append(rule)
            rules['confidence'][rule] = 0.9

        self.logger.info(f"Detected {len(rules['detected_rules'])} strategy rules")
        return rules

    def find_weaknesses(self) -> Dict:
        """
        Identify weaknesses in the EA's strategy

        Returns:
            Dictionary with identified weaknesses and improvement opportunities
        """
        self.logger.info("Analyzing EA weaknesses...")

        trades_df = self.monitor.get_trades_dataframe()
        closed_trades = trades_df[trades_df['exit_time'].notna()].copy()

        if closed_trades.empty:
            return {'error': 'No closed trades to analyze'}

        weaknesses = {
            'issues': [],
            'opportunities': []
        }

        # Check win rate
        win_rate = (closed_trades['profit'] > 0).sum() / len(closed_trades) * 100

        if win_rate < 50:
            weaknesses['issues'].append({
                'type': 'low_win_rate',
                'description': f"Win rate is only {win_rate:.1f}%",
                'severity': 'high'
            })
            weaknesses['opportunities'].append("Improve entry timing to increase win rate")

        # Check if losers are bigger than winners
        winners = closed_trades[closed_trades['profit'] > 0]
        losers = closed_trades[closed_trades['profit'] < 0]

        if not winners.empty and not losers.empty:
            avg_win = winners['profit'].mean()
            avg_loss = abs(losers['profit'].mean())

            if avg_loss > avg_win * 1.5:
                weaknesses['issues'].append({
                    'type': 'poor_risk_reward',
                    'description': f"Average loss (${avg_loss:.2f}) is much larger than average win (${avg_win:.2f})",
                    'severity': 'high'
                })
                weaknesses['opportunities'].append("Tighten stop losses or widen take profits")

        # Check for long losing streaks
        closed_trades = closed_trades.sort_values('entry_time')
        closed_trades['is_win'] = closed_trades['profit'] > 0

        max_losing_streak = 0
        current_streak = 0

        for is_win in closed_trades['is_win']:
            if not is_win:
                current_streak += 1
                max_losing_streak = max(max_losing_streak, current_streak)
            else:
                current_streak = 0

        if max_losing_streak >= 5:
            weaknesses['issues'].append({
                'type': 'long_losing_streaks',
                'description': f"Maximum losing streak: {max_losing_streak} trades",
                'severity': 'medium'
            })
            weaknesses['opportunities'].append("Add circuit breaker to stop trading after consecutive losses")

        # Check for time-based weaknesses
        if 'hour' in closed_trades.columns:
            # Performance by hour
            hourly_performance = closed_trades.groupby('hour')['profit'].agg(['sum', 'count'])

            if len(hourly_performance) > 3:
                worst_hours = hourly_performance.nsmallest(3, 'sum')

                for hour, row in worst_hours.iterrows():
                    if row['count'] >= 3 and row['sum'] < 0:
                        weaknesses['issues'].append({
                            'type': 'poor_timing',
                            'description': f"Losing money at hour {hour}:00 (${row['sum']:.2f} over {row['count']} trades)",
                            'severity': 'low'
                        })

                weaknesses['opportunities'].append("Avoid trading during consistently losing hours")

        # Check if EA is overtrading
        if len(closed_trades) > 0:
            date_range = (closed_trades['exit_time'].max() - closed_trades['entry_time'].min()).days
            trades_per_day = len(closed_trades) / max(date_range, 1)

            if trades_per_day > 10:
                weaknesses['issues'].append({
                    'type': 'overtrading',
                    'description': f"High frequency: {trades_per_day:.1f} trades per day",
                    'severity': 'medium'
                })
                weaknesses['opportunities'].append("Add filters to reduce trade frequency and increase quality")

        self.logger.info(f"Identified {len(weaknesses['issues'])} weaknesses")
        return weaknesses

    def generate_full_report(self) -> Dict:
        """
        Generate comprehensive analysis report

        Returns:
            Dictionary with complete EA analysis
        """
        self.logger.info("Generating full EA analysis report...")

        report = {
            'statistics': self.monitor.get_ea_statistics(),
            'entry_patterns': self.analyze_entry_patterns(),
            'exit_patterns': self.analyze_exit_patterns(),
            'detected_rules': self.detect_strategy_rules(),
            'weaknesses': self.find_weaknesses(),
            'generated_at': pd.Timestamp.now()
        }

        return report
