"""
Performance Analysis Module
Analyzes backtest results and generates reports
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json


class PerformanceAnalyzer:
    """Analyze backtest performance and generate reports"""

    def __init__(self, results: Dict):
        """
        Initialize performance analyzer

        Args:
            results: Results dict from Backtester.get_results()
        """
        self.results = results
        self.stats = results['statistics']
        self.trades = results['trades']
        self.trades_df = pd.DataFrame(self.trades) if len(self.trades) > 0 else pd.DataFrame()

    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """
        Calculate Sharpe ratio

        Args:
            risk_free_rate: Annual risk-free rate (default 2%)

        Returns:
            Sharpe ratio
        """
        if len(self.trades_df) == 0:
            return 0.0

        # Calculate daily returns
        self.trades_df['date'] = pd.to_datetime(self.trades_df['time_close']).dt.date
        daily_profits = self.trades_df.groupby('date')['profit'].sum()

        if len(daily_profits) == 0:
            return 0.0

        # Annualize returns
        mean_return = daily_profits.mean() * 252  # Trading days per year
        std_return = daily_profits.std() * np.sqrt(252)

        if std_return == 0:
            return 0.0

        sharpe = (mean_return - risk_free_rate) / std_return
        return sharpe

    def calculate_sortino_ratio(self, risk_free_rate: float = 0.02) -> float:
        """
        Calculate Sortino ratio (only penalizes downside volatility)

        Args:
            risk_free_rate: Annual risk-free rate (default 2%)

        Returns:
            Sortino ratio
        """
        if len(self.trades_df) == 0:
            return 0.0

        # Calculate daily returns
        self.trades_df['date'] = pd.to_datetime(self.trades_df['time_close']).dt.date
        daily_profits = self.trades_df.groupby('date')['profit'].sum()

        if len(daily_profits) == 0:
            return 0.0

        # Annualize returns
        mean_return = daily_profits.mean() * 252

        # Downside deviation (only negative returns)
        downside_returns = daily_profits[daily_profits < 0]
        if len(downside_returns) == 0:
            return np.inf

        downside_std = downside_returns.std() * np.sqrt(252)

        if downside_std == 0:
            return np.inf

        sortino = (mean_return - risk_free_rate) / downside_std
        return sortino

    def calculate_calmar_ratio(self) -> float:
        """
        Calculate Calmar ratio (annual return / max drawdown)

        Returns:
            Calmar ratio
        """
        max_dd = self.results['max_drawdown']
        if max_dd == 0:
            return 0.0

        annual_return = self.stats['net_profit']
        calmar = annual_return / max_dd
        return calmar

    def analyze_drawdowns(self) -> Dict:
        """
        Analyze drawdown periods

        Returns:
            Dict with drawdown statistics
        """
        if len(self.trades_df) == 0:
            return {
                'max_drawdown': 0,
                'avg_drawdown': 0,
                'max_drawdown_duration_days': 0,
                'drawdown_periods': []
            }

        # Calculate equity curve
        trades_sorted = self.trades_df.sort_values('time_close')
        trades_sorted['cumulative_profit'] = trades_sorted['profit'].cumsum()
        trades_sorted['equity'] = self.stats['initial_balance'] + trades_sorted['cumulative_profit']

        # Calculate drawdown
        trades_sorted['peak'] = trades_sorted['equity'].cummax()
        trades_sorted['drawdown'] = trades_sorted['peak'] - trades_sorted['equity']
        trades_sorted['drawdown_pct'] = (trades_sorted['drawdown'] / trades_sorted['peak']) * 100

        # Find drawdown periods
        in_drawdown = trades_sorted['drawdown'] > 0
        drawdown_periods = []

        if in_drawdown.any():
            # Group consecutive drawdown periods
            trades_sorted['dd_group'] = (in_drawdown != in_drawdown.shift()).cumsum()

            for group_id in trades_sorted[in_drawdown]['dd_group'].unique():
                period = trades_sorted[trades_sorted['dd_group'] == group_id]

                start_time = period.iloc[0]['time_close']
                end_time = period.iloc[-1]['time_close']
                duration = (end_time - start_time).total_seconds() / 86400  # Days

                max_dd_in_period = period['drawdown'].max()
                max_dd_pct_in_period = period['drawdown_pct'].max()

                drawdown_periods.append({
                    'start': start_time,
                    'end': end_time,
                    'duration_days': duration,
                    'max_drawdown': max_dd_in_period,
                    'max_drawdown_pct': max_dd_pct_in_period
                })

        max_dd_duration = max([p['duration_days'] for p in drawdown_periods]) if drawdown_periods else 0

        return {
            'max_drawdown': self.results['max_drawdown'],
            'max_drawdown_pct': (self.results['max_drawdown'] / self.stats['initial_balance']) * 100,
            'avg_drawdown': trades_sorted['drawdown'].mean(),
            'max_drawdown_duration_days': max_dd_duration,
            'drawdown_periods': drawdown_periods
        }

    def analyze_consecutive_trades(self) -> Dict:
        """
        Analyze consecutive wins/losses

        Returns:
            Dict with consecutive trade statistics
        """
        if len(self.trades_df) == 0:
            return {
                'max_consecutive_wins': 0,
                'max_consecutive_losses': 0,
                'avg_consecutive_wins': 0,
                'avg_consecutive_losses': 0
            }

        trades_sorted = self.trades_df.sort_values('time_close')
        trades_sorted['is_win'] = trades_sorted['profit'] > 0

        # Count consecutive wins/losses
        consecutive_wins = []
        consecutive_losses = []

        current_streak = 0
        current_type = None

        for is_win in trades_sorted['is_win']:
            if is_win:
                if current_type == 'win':
                    current_streak += 1
                else:
                    if current_type == 'loss' and current_streak > 0:
                        consecutive_losses.append(current_streak)
                    current_streak = 1
                    current_type = 'win'
            else:
                if current_type == 'loss':
                    current_streak += 1
                else:
                    if current_type == 'win' and current_streak > 0:
                        consecutive_wins.append(current_streak)
                    current_streak = 1
                    current_type = 'loss'

        # Add final streak
        if current_type == 'win' and current_streak > 0:
            consecutive_wins.append(current_streak)
        elif current_type == 'loss' and current_streak > 0:
            consecutive_losses.append(current_streak)

        return {
            'max_consecutive_wins': max(consecutive_wins) if consecutive_wins else 0,
            'max_consecutive_losses': max(consecutive_losses) if consecutive_losses else 0,
            'avg_consecutive_wins': np.mean(consecutive_wins) if consecutive_wins else 0,
            'avg_consecutive_losses': np.mean(consecutive_losses) if consecutive_losses else 0
        }

    def analyze_by_hour(self) -> Dict:
        """
        Analyze performance by hour of day

        Returns:
            Dict mapping hour -> performance metrics
        """
        if len(self.trades_df) == 0:
            return {}

        self.trades_df['hour'] = pd.to_datetime(self.trades_df['time']).dt.hour

        hourly_stats = {}
        for hour in range(24):
            hour_trades = self.trades_df[self.trades_df['hour'] == hour]

            if len(hour_trades) == 0:
                continue

            wins = (hour_trades['profit'] > 0).sum()
            losses = (hour_trades['profit'] < 0).sum()
            total = len(hour_trades)

            hourly_stats[hour] = {
                'total_trades': total,
                'wins': wins,
                'losses': losses,
                'win_rate': (wins / total * 100) if total > 0 else 0,
                'total_profit': hour_trades['profit'].sum(),
                'avg_profit': hour_trades['profit'].mean()
            }

        return hourly_stats

    def analyze_by_day_of_week(self) -> Dict:
        """
        Analyze performance by day of week

        Returns:
            Dict mapping day -> performance metrics
        """
        if len(self.trades_df) == 0:
            return {}

        self.trades_df['day_of_week'] = pd.to_datetime(self.trades_df['time']).dt.dayofweek

        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        daily_stats = {}

        for day_num, day_name in enumerate(day_names):
            day_trades = self.trades_df[self.trades_df['day_of_week'] == day_num]

            if len(day_trades) == 0:
                continue

            wins = (day_trades['profit'] > 0).sum()
            losses = (day_trades['profit'] < 0).sum()
            total = len(day_trades)

            daily_stats[day_name] = {
                'total_trades': total,
                'wins': wins,
                'losses': losses,
                'win_rate': (wins / total * 100) if total > 0 else 0,
                'total_profit': day_trades['profit'].sum(),
                'avg_profit': day_trades['profit'].mean()
            }

        return daily_stats

    def analyze_by_strategy(self) -> Dict:
        """
        Analyze performance by strategy type

        Returns:
            Dict mapping strategy -> performance metrics
        """
        if len(self.trades_df) == 0:
            return {}

        # Extract strategy from comment
        self.trades_df['strategy'] = self.trades_df['comment'].apply(
            lambda x: 'Breakout' if 'Breakout' in x
            else 'Mean Reversion' if 'Confluence' in x
            else 'Recovery' if any(kw in x for kw in ['Grid', 'Hedge', 'DCA'])
            else 'Other'
        )

        strategy_stats = {}
        for strategy in self.trades_df['strategy'].unique():
            strategy_trades = self.trades_df[self.trades_df['strategy'] == strategy]

            wins = (strategy_trades['profit'] > 0).sum()
            losses = (strategy_trades['profit'] < 0).sum()
            total = len(strategy_trades)

            strategy_stats[strategy] = {
                'total_trades': total,
                'wins': wins,
                'losses': losses,
                'win_rate': (wins / total * 100) if total > 0 else 0,
                'total_profit': strategy_trades['profit'].sum(),
                'avg_profit': strategy_trades['profit'].mean(),
                'avg_duration_hours': (
                    (strategy_trades['time_close'] - strategy_trades['time']).dt.total_seconds() / 3600
                ).mean()
            }

        return strategy_stats

    def generate_report(self, output_file: Optional[str] = None) -> str:
        """
        Generate comprehensive performance report

        Args:
            output_file: Optional file path to save report

        Returns:
            Report as string
        """
        lines = []
        lines.append("=" * 100)
        lines.append("BACKTEST PERFORMANCE REPORT")
        lines.append("=" * 100)

        # Basic statistics
        lines.append("\n📊 BASIC STATISTICS")
        lines.append("-" * 100)
        lines.append(f"Initial Balance:        ${self.stats['initial_balance']:>15,.2f}")
        lines.append(f"Final Balance:          ${self.stats['final_balance']:>15,.2f}")
        lines.append(f"Final Equity:           ${self.stats['final_equity']:>15,.2f}")
        lines.append(f"Net Profit:             ${self.stats['net_profit']:>15,.2f}")
        lines.append(f"Return:                 {(self.stats['net_profit'] / self.stats['initial_balance'] * 100):>15.2f}%")
        lines.append(f"Total Trades:           {self.stats['total_trades']:>15}")
        lines.append(f"Win Rate:               {self.stats['win_rate']:>15.2f}%")
        lines.append(f"Profit Factor:          {self.stats['profit_factor']:>15.2f}")

        # Risk metrics
        lines.append("\n📉 RISK METRICS")
        lines.append("-" * 100)
        sharpe = self.calculate_sharpe_ratio()
        sortino = self.calculate_sortino_ratio()
        calmar = self.calculate_calmar_ratio()

        lines.append(f"Sharpe Ratio:           {sharpe:>15.2f}")
        lines.append(f"Sortino Ratio:          {sortino:>15.2f}")
        lines.append(f"Calmar Ratio:           {calmar:>15.2f}")
        lines.append(f"Max Drawdown:           ${self.results['max_drawdown']:>15,.2f}")

        # Drawdown analysis
        dd_analysis = self.analyze_drawdowns()
        lines.append(f"Max Drawdown %:         {dd_analysis['max_drawdown_pct']:>15.2f}%")
        lines.append(f"Avg Drawdown:           ${dd_analysis['avg_drawdown']:>15,.2f}")
        lines.append(f"Max DD Duration:        {dd_analysis['max_drawdown_duration_days']:>15.1f} days")

        # Consecutive trades
        consec = self.analyze_consecutive_trades()
        lines.append("\n🔄 CONSECUTIVE TRADES")
        lines.append("-" * 100)
        lines.append(f"Max Consecutive Wins:   {consec['max_consecutive_wins']:>15}")
        lines.append(f"Max Consecutive Losses: {consec['max_consecutive_losses']:>15}")
        lines.append(f"Avg Consecutive Wins:   {consec['avg_consecutive_wins']:>15.1f}")
        lines.append(f"Avg Consecutive Losses: {consec['avg_consecutive_losses']:>15.1f}")

        # Performance by symbol
        lines.append("\n📍 PERFORMANCE BY SYMBOL")
        lines.append("-" * 100)
        for symbol, profit in self.results['profit_by_symbol'].items():
            symbol_trades = self.trades_df[self.trades_df['symbol'] == symbol]
            wins = (symbol_trades['profit'] > 0).sum()
            total = len(symbol_trades)
            wr = (wins / total * 100) if total > 0 else 0

            lines.append(f"{symbol:>10}: ${profit:>12,.2f}  |  {total:>4} trades  |  {wr:>5.1f}% win rate")

        # Performance by strategy
        strategy_stats = self.analyze_by_strategy()
        lines.append("\n🎯 PERFORMANCE BY STRATEGY")
        lines.append("-" * 100)
        for strategy, stats in strategy_stats.items():
            lines.append(
                f"{strategy:>15}: ${stats['total_profit']:>12,.2f}  |  "
                f"{stats['total_trades']:>4} trades  |  "
                f"{stats['win_rate']:>5.1f}% win rate  |  "
                f"{stats['avg_duration_hours']:>5.1f}h avg duration"
            )

        # Performance by day of week
        daily_stats = self.analyze_by_day_of_week()
        if daily_stats:
            lines.append("\n📅 PERFORMANCE BY DAY OF WEEK")
            lines.append("-" * 100)
            for day, stats in daily_stats.items():
                lines.append(
                    f"{day:>10}: ${stats['total_profit']:>12,.2f}  |  "
                    f"{stats['total_trades']:>4} trades  |  "
                    f"{stats['win_rate']:>5.1f}% win rate"
                )

        # Performance by hour
        hourly_stats = self.analyze_by_hour()
        if hourly_stats:
            lines.append("\n🕐 PERFORMANCE BY HOUR (Top 5)")
            lines.append("-" * 100)
            sorted_hours = sorted(hourly_stats.items(), key=lambda x: x[1]['total_profit'], reverse=True)[:5]
            for hour, stats in sorted_hours:
                lines.append(
                    f"Hour {hour:>2}:00: ${stats['total_profit']:>12,.2f}  |  "
                    f"{stats['total_trades']:>4} trades  |  "
                    f"{stats['win_rate']:>5.1f}% win rate"
                )

        lines.append("\n" + "=" * 100)

        report = "\n".join(lines)

        # Save to file if requested
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)

        return report

    def export_trades_to_csv(self, filepath: str) -> None:
        """
        Export trade history to CSV

        Args:
            filepath: Output CSV file path
        """
        if len(self.trades_df) == 0:
            return

        self.trades_df.to_csv(filepath, index=False)

    def export_equity_curve_to_csv(self, filepath: str) -> None:
        """
        Export equity curve to CSV

        Args:
            filepath: Output CSV file path
        """
        if len(self.trades_df) == 0:
            return

        trades_sorted = self.trades_df.sort_values('time_close')
        trades_sorted['cumulative_profit'] = trades_sorted['profit'].cumsum()
        trades_sorted['equity'] = self.stats['initial_balance'] + trades_sorted['cumulative_profit']

        equity_curve = trades_sorted[['time_close', 'equity', 'cumulative_profit']].copy()
        equity_curve.columns = ['timestamp', 'equity', 'cumulative_profit']

        equity_curve.to_csv(filepath, index=False)
