"""
Recovery Analyzer - Evaluates recovery mechanism effectiveness

Analyzes:
- DCA effectiveness and success rate
- Hedge effectiveness and drawdown reduction
- Grid effectiveness and averaging success
- Stack metrics (size, duration, cost)
"""

from typing import Dict, List, Optional
from datetime import datetime
import statistics


class RecoveryAnalyzer:
    """Analyzes recovery mechanism effectiveness"""

    def __init__(self):
        """Initialize recovery analyzer"""
        pass

    def analyze_recovery_effectiveness(self, recovery_actions: List[Dict]) -> Dict:
        """
        Analyze overall recovery effectiveness

        Args:
            recovery_actions: List of recovery action records

        Returns:
            Dict with effectiveness metrics by type
        """
        if not recovery_actions:
            return self._empty_analysis()

        analysis = {}

        # Analyze each recovery type
        for recovery_type in ['grid', 'hedge', 'dca']:
            type_actions = [a for a in recovery_actions if a.get('type') == recovery_type]
            analysis[recovery_type] = self._analyze_recovery_type(type_actions)

        # Overall stack metrics
        analysis['stack_metrics'] = self._analyze_stack_metrics(recovery_actions)

        return analysis

    def _analyze_recovery_type(self, actions: List[Dict]) -> Dict:
        """Analyze specific recovery type effectiveness"""
        if not actions:
            return {
                'total_triggered': 0,
                'successful': 0,
                'failed': 0,
                'success_rate': 0,
                'avg_levels': 0,
                'avg_cost': 0,
                'avg_duration_minutes': 0,
            }

        metrics = {}
        metrics['total_triggered'] = len(actions)
        metrics['successful'] = sum(1 for a in actions if a.get('recovered', False))
        metrics['failed'] = metrics['total_triggered'] - metrics['successful']
        metrics['success_rate'] = (metrics['successful'] / metrics['total_triggered'] * 100) if metrics['total_triggered'] > 0 else 0

        # Level analysis
        levels = [a.get('level', 1) for a in actions]
        metrics['avg_levels'] = statistics.mean(levels) if levels else 0
        metrics['max_levels'] = max(levels) if levels else 0

        # Cost analysis
        costs = [a.get('cost', 0) for a in actions if 'cost' in a]
        metrics['avg_cost'] = statistics.mean(costs) if costs else 0

        # Duration analysis
        durations = [a.get('duration_minutes', 0) for a in actions if 'duration_minutes' in a]
        metrics['avg_duration_minutes'] = statistics.mean(durations) if durations else 0

        return metrics

    def _analyze_stack_metrics(self, recovery_actions: List[Dict]) -> Dict:
        """Analyze recovery stack metrics"""
        # Group by parent ticket to analyze stacks
        stacks = {}

        for action in recovery_actions:
            parent = action.get('parent_ticket')
            if not parent:
                continue

            if parent not in stacks:
                stacks[parent] = {
                    'actions': [],
                    'max_drawdown': 0,
                    'max_volume': 0,
                    'final_profit': 0,
                }

            stacks[parent]['actions'].append(action)
            stacks[parent]['max_drawdown'] = max(
                stacks[parent]['max_drawdown'],
                abs(action.get('drawdown', 0))
            )
            stacks[parent]['max_volume'] = max(
                stacks[parent]['max_volume'],
                action.get('total_volume', 0)
            )

        if not stacks:
            return {
                'total_stacks': 0,
                'avg_max_drawdown': 0,
                'avg_max_volume': 0,
                'avg_recovery_count': 0,
            }

        drawdowns = [s['max_drawdown'] for s in stacks.values()]
        volumes = [s['max_volume'] for s in stacks.values()]
        action_counts = [len(s['actions']) for s in stacks.values()]

        return {
            'total_stacks': len(stacks),
            'avg_max_drawdown': statistics.mean(drawdowns) if drawdowns else 0,
            'max_drawdown': max(drawdowns) if drawdowns else 0,
            'avg_max_volume': statistics.mean(volumes) if volumes else 0,
            'max_volume': max(volumes) if volumes else 0,
            'avg_recovery_count': statistics.mean(action_counts) if action_counts else 0,
        }

    def _empty_analysis(self) -> Dict:
        """Return empty analysis"""
        return {
            'grid': self._analyze_recovery_type([]),
            'hedge': self._analyze_recovery_type([]),
            'dca': self._analyze_recovery_type([]),
            'stack_metrics': {
                'total_stacks': 0,
                'avg_max_drawdown': 0,
                'avg_max_volume': 0,
                'avg_recovery_count': 0,
            },
        }

    def compare_with_baseline(
        self,
        current_metrics: Dict,
        baseline_stats: Optional[Dict] = None
    ) -> Dict:
        """
        Compare current recovery performance with baseline

        Args:
            current_metrics: Current recovery metrics
            baseline_stats: Baseline from bootstrap_statistics.json

        Returns:
            Dict with comparison and trends
        """
        if not baseline_stats:
            return {}

        comparison = {}

        # Compare drawdowns
        baseline_drawdown = baseline_stats.get('drawdown', {}).get('mean', 0)
        current_drawdown = current_metrics.get('stack_metrics', {}).get('avg_max_drawdown', 0)

        if baseline_drawdown > 0:
            drawdown_change = ((current_drawdown - baseline_drawdown) / baseline_drawdown) * 100
            comparison['drawdown_vs_baseline'] = {
                'current': current_drawdown,
                'baseline': baseline_drawdown,
                'change_percent': drawdown_change,
                'trend': 'improving' if drawdown_change < 0 else 'worsening',
            }

        # Compare volumes
        baseline_volume = baseline_stats.get('volume', {}).get('mean', 0)
        current_volume = current_metrics.get('stack_metrics', {}).get('avg_max_volume', 0)

        if baseline_volume > 0:
            volume_change = ((current_volume - baseline_volume) / baseline_volume) * 100
            comparison['volume_vs_baseline'] = {
                'current': current_volume,
                'baseline': baseline_volume,
                'change_percent': volume_change,
                'trend': 'increasing' if volume_change > 0 else 'decreasing',
            }

        return comparison

    def identify_recovery_patterns(self, recovery_actions: List[Dict]) -> List[Dict]:
        """
        Identify patterns in recovery effectiveness

        Args:
            recovery_actions: List of recovery action records

        Returns:
            List of identified patterns
        """
        patterns = []

        if not recovery_actions:
            return patterns

        # Analyze each type
        for recovery_type in ['grid', 'hedge', 'dca']:
            type_actions = [a for a in recovery_actions if a.get('type') == recovery_type]

            if len(type_actions) < 5:
                continue

            metrics = self._analyze_recovery_type(type_actions)

            # Pattern: High success rate
            if metrics['success_rate'] > 80:
                patterns.append({
                    'type': 'high_effectiveness',
                    'recovery_type': recovery_type,
                    'success_rate': metrics['success_rate'],
                    'message': f"{recovery_type.upper()} shows high effectiveness ({metrics['success_rate']:.1f}% success rate)",
                })

            # Pattern: Low success rate
            if metrics['success_rate'] < 50:
                patterns.append({
                    'type': 'low_effectiveness',
                    'recovery_type': recovery_type,
                    'success_rate': metrics['success_rate'],
                    'message': f"{recovery_type.upper()} shows low effectiveness ({metrics['success_rate']:.1f}% success rate) - consider tuning",
                })

            # Pattern: Many levels needed
            if metrics['avg_levels'] > 4:
                patterns.append({
                    'type': 'high_recovery_depth',
                    'recovery_type': recovery_type,
                    'avg_levels': metrics['avg_levels'],
                    'message': f"{recovery_type.upper()} requires many levels (avg {metrics['avg_levels']:.1f}) - may indicate poor entry timing",
                })

        return patterns
