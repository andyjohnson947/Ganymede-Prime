"""
Performance Analyzer - Tracks robot trading performance

Analyzes:
- Win rate by market condition
- Profit factor and risk metrics
- Trade duration and efficiency
- Correlation with market factors
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import statistics


class PerformanceAnalyzer:
    """Analyzes robot trading performance and correlates with market conditions"""

    def __init__(self):
        """Initialize performance analyzer"""
        pass

    def analyze_performance(self, trades: List[Dict], hours: int = 24) -> Dict:
        """
        Analyze trading performance

        Args:
            trades: List of trade records
            hours: Time window for analysis

        Returns:
            Dict with performance metrics
        """
        if not trades:
            return self._empty_performance()

        # Filter to time window
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_trades = [
            t for t in trades
            if datetime.fromisoformat(t['timestamp']) > cutoff
        ]

        if not recent_trades:
            return self._empty_performance()

        metrics = {}

        # Basic metrics
        metrics['total_trades'] = len(recent_trades)
        metrics['wins'] = sum(1 for t in recent_trades if t.get('profit', 0) > 0)
        metrics['losses'] = metrics['total_trades'] - metrics['wins']
        metrics['win_rate'] = (metrics['wins'] / metrics['total_trades'] * 100) if metrics['total_trades'] > 0 else 0

        # Profit metrics
        profits = [t.get('profit', 0) for t in recent_trades]
        metrics['total_profit'] = sum(profits)
        metrics['avg_profit'] = statistics.mean(profits) if profits else 0
        metrics['max_profit'] = max(profits) if profits else 0
        metrics['max_loss'] = min(profits) if profits else 0

        # Profit factor
        gross_profit = sum(p for p in profits if p > 0)
        gross_loss = abs(sum(p for p in profits if p < 0))
        metrics['profit_factor'] = (gross_profit / gross_loss) if gross_loss > 0 else 0

        # Duration analysis
        durations = [t.get('duration_minutes', 0) for t in recent_trades if 'duration_minutes' in t]
        if durations:
            metrics['avg_duration_minutes'] = statistics.mean(durations)
            metrics['max_duration_minutes'] = max(durations)

        # By market regime
        metrics['by_regime'] = self._analyze_by_regime(recent_trades)

        # By time of day
        metrics['by_hour'] = self._analyze_by_hour(recent_trades)

        return metrics

    def _analyze_by_regime(self, trades: List[Dict]) -> Dict:
        """Analyze performance by market regime"""
        regime_stats = {}

        for trade in trades:
            regime = trade.get('market_regime', 'unknown')

            if regime not in regime_stats:
                regime_stats[regime] = {
                    'trades': 0,
                    'wins': 0,
                    'total_profit': 0.0,
                }

            regime_stats[regime]['trades'] += 1
            if trade.get('profit', 0) > 0:
                regime_stats[regime]['wins'] += 1
            regime_stats[regime]['total_profit'] += trade.get('profit', 0)

        # Calculate percentages
        for regime, stats in regime_stats.items():
            stats['win_rate'] = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
            stats['avg_profit'] = stats['total_profit'] / stats['trades'] if stats['trades'] > 0 else 0

        return regime_stats

    def _analyze_by_hour(self, trades: List[Dict]) -> Dict:
        """Analyze performance by hour of day"""
        hour_stats = {}

        for trade in trades:
            try:
                hour = datetime.fromisoformat(trade['timestamp']).hour
                if hour not in hour_stats:
                    hour_stats[hour] = {
                        'trades': 0,
                        'wins': 0,
                        'total_profit': 0.0,
                    }

                hour_stats[hour]['trades'] += 1
                if trade.get('profit', 0) > 0:
                    hour_stats[hour]['wins'] += 1
                hour_stats[hour]['total_profit'] += trade.get('profit', 0)
            except:
                continue

        # Calculate percentages
        for hour, stats in hour_stats.items():
            stats['win_rate'] = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0

        return hour_stats

    def _empty_performance(self) -> Dict:
        """Return empty performance metrics"""
        return {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
            'total_profit': 0,
            'avg_profit': 0,
            'max_profit': 0,
            'max_loss': 0,
            'profit_factor': 0,
            'by_regime': {},
            'by_hour': {},
        }

    def identify_patterns(self, trades: List[Dict], market_conditions: List[Dict]) -> List[Dict]:
        """
        Identify performance patterns

        Args:
            trades: List of trade records
            market_conditions: List of market condition snapshots

        Returns:
            List of identified patterns with insights
        """
        patterns = []

        if not trades:
            return patterns

        # Pattern 1: High loss rate in specific regime
        regime_stats = self._analyze_by_regime(trades)
        for regime, stats in regime_stats.items():
            if stats['trades'] >= 5 and stats['win_rate'] < 40:
                patterns.append({
                    'type': 'low_win_rate',
                    'severity': 'high',
                    'regime': regime,
                    'win_rate': stats['win_rate'],
                    'trades': stats['trades'],
                    'message': f"Low win rate ({stats['win_rate']:.1f}%) in {regime} market - consider avoiding",
                })

        # Pattern 2: Consistently profitable regime
        for regime, stats in regime_stats.items():
            if stats['trades'] >= 5 and stats['win_rate'] > 70:
                patterns.append({
                    'type': 'high_win_rate',
                    'severity': 'info',
                    'regime': regime,
                    'win_rate': stats['win_rate'],
                    'trades': stats['trades'],
                    'message': f"High win rate ({stats['win_rate']:.1f}%) in {regime} market - optimal conditions",
                })

        # Pattern 3: Large losses
        large_losses = [t for t in trades if t.get('profit', 0) < -50]
        if len(large_losses) >= 3:
            loss_regimes = [t.get('market_regime', 'unknown') for t in large_losses]
            most_common = max(set(loss_regimes), key=loss_regimes.count) if loss_regimes else 'unknown'

            patterns.append({
                'type': 'large_losses',
                'severity': 'critical',
                'count': len(large_losses),
                'common_regime': most_common,
                'message': f"{len(large_losses)} large losses (>${50}) detected, mostly in {most_common} market",
            })

        return patterns
