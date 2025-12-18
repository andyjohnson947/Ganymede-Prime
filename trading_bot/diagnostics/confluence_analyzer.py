"""
Confluence Analyzer - Evaluates which confluence combinations work best

Analyzes:
- Success rate by confluence score (4, 5, 6, 7+)
- Performance by individual confluence factors
- Breakout vs mean reversion effectiveness
- HTF signal contributions
- Best-performing confluence stacks
"""

from typing import Dict, List, Optional
from collections import defaultdict
import statistics


class ConfluenceAnalyzer:
    """Analyzes confluence signal effectiveness"""

    def __init__(self):
        """Initialize confluence analyzer"""
        pass

    def analyze_confluence_effectiveness(self, trades: List[Dict]) -> Dict:
        """
        Analyze overall confluence effectiveness

        Args:
            trades: List of trade records with confluence data

        Returns:
            Dict with effectiveness metrics by confluence patterns
        """
        if not trades:
            return self._empty_analysis()

        # Filter trades with confluence data
        confluence_trades = [t for t in trades if t.get('confluence_score') is not None]

        if not confluence_trades:
            return self._empty_analysis()

        analysis = {}

        # 1. Performance by confluence score
        analysis['by_score'] = self._analyze_by_score(confluence_trades)

        # 2. Performance by individual factors
        analysis['by_factor'] = self._analyze_by_factor(confluence_trades)

        # 3. Strategy mode performance (breakout vs mean reversion)
        analysis['by_strategy'] = self._analyze_by_strategy(confluence_trades)

        # 4. Breakout effectiveness
        analysis['breakout_analysis'] = self._analyze_breakouts(confluence_trades)

        # 5. HTF signal contributions
        analysis['htf_analysis'] = self._analyze_htf_signals(confluence_trades)

        # 6. Best performing confluence stacks
        analysis['top_stacks'] = self._identify_top_stacks(confluence_trades)

        return analysis

    def _analyze_by_score(self, trades: List[Dict]) -> Dict:
        """Analyze performance by confluence score"""
        score_buckets = {
            '4': [],    # Minimum score
            '5': [],    # Moderate
            '6': [],    # Strong
            '7+': [],   # Very strong
        }

        for trade in trades:
            score = trade.get('confluence_score', 0)
            profit = trade.get('profit', 0)

            if score == 4:
                score_buckets['4'].append(profit)
            elif score == 5:
                score_buckets['5'].append(profit)
            elif score == 6:
                score_buckets['6'].append(profit)
            elif score >= 7:
                score_buckets['7+'].append(profit)

        results = {}
        for score_range, profits in score_buckets.items():
            if profits:
                wins = sum(1 for p in profits if p > 0)
                losses = len(profits) - wins
                results[score_range] = {
                    'total_trades': len(profits),
                    'wins': wins,
                    'losses': losses,
                    'win_rate': (wins / len(profits) * 100) if profits else 0,
                    'avg_profit': statistics.mean(profits),
                    'total_profit': sum(profits),
                }
            else:
                results[score_range] = self._empty_bucket_metrics()

        return results

    def _analyze_by_factor(self, trades: List[Dict]) -> Dict:
        """Analyze performance by individual confluence factors"""
        factor_performance = defaultdict(lambda: {'wins': 0, 'losses': 0, 'profits': []})

        for trade in trades:
            factors = trade.get('confluence_factors', [])
            profit = trade.get('profit', 0)

            for factor in factors:
                factor_performance[factor]['profits'].append(profit)
                if profit > 0:
                    factor_performance[factor]['wins'] += 1
                else:
                    factor_performance[factor]['losses'] += 1

        results = {}
        for factor, data in factor_performance.items():
            total = data['wins'] + data['losses']
            results[factor] = {
                'total_trades': total,
                'wins': data['wins'],
                'losses': data['losses'],
                'win_rate': (data['wins'] / total * 100) if total > 0 else 0,
                'avg_profit': statistics.mean(data['profits']) if data['profits'] else 0,
                'total_profit': sum(data['profits']),
            }

        # Sort by win rate
        results = dict(sorted(results.items(), key=lambda x: x[1]['win_rate'], reverse=True))

        return results

    def _analyze_by_strategy(self, trades: List[Dict]) -> Dict:
        """Analyze performance by strategy mode"""
        strategy_buckets = {
            'breakout': [],
            'mean_reversion': [],
            'unknown': [],
        }

        for trade in trades:
            strategy = trade.get('strategy_mode', 'unknown')
            profit = trade.get('profit', 0)

            if strategy in strategy_buckets:
                strategy_buckets[strategy].append(profit)
            else:
                strategy_buckets['unknown'].append(profit)

        results = {}
        for strategy, profits in strategy_buckets.items():
            if profits:
                wins = sum(1 for p in profits if p > 0)
                losses = len(profits) - wins
                results[strategy] = {
                    'total_trades': len(profits),
                    'wins': wins,
                    'losses': losses,
                    'win_rate': (wins / len(profits) * 100) if profits else 0,
                    'avg_profit': statistics.mean(profits),
                    'total_profit': sum(profits),
                }
            else:
                results[strategy] = self._empty_bucket_metrics()

        return results

    def _analyze_breakouts(self, trades: List[Dict]) -> Dict:
        """Analyze breakout-specific metrics"""
        breakout_trades = [t for t in trades if t.get('breakout_info', {}).get('is_breakout')]

        if not breakout_trades:
            return {
                'total_breakouts': 0,
                'avg_levels_broken': 0,
                'win_rate': 0,
                'avg_profit': 0,
            }

        profits = [t.get('profit', 0) for t in breakout_trades]
        wins = sum(1 for p in profits if p > 0)

        levels_broken = []
        for trade in breakout_trades:
            breakout_info = trade.get('breakout_info', {})
            count = breakout_info.get('levels_broken_count', 0)
            if count > 0:
                levels_broken.append(count)

        return {
            'total_breakouts': len(breakout_trades),
            'avg_levels_broken': statistics.mean(levels_broken) if levels_broken else 0,
            'wins': wins,
            'losses': len(profits) - wins,
            'win_rate': (wins / len(profits) * 100) if profits else 0,
            'avg_profit': statistics.mean(profits),
            'total_profit': sum(profits),
        }

    def _analyze_htf_signals(self, trades: List[Dict]) -> Dict:
        """Analyze HTF (higher timeframe) signal contributions"""
        htf_trades = [t for t in trades if t.get('htf_signals', {}).get('score', 0) > 0]

        if not htf_trades:
            return {
                'total_with_htf': 0,
                'win_rate': 0,
                'avg_htf_score': 0,
            }

        profits = [t.get('profit', 0) for t in htf_trades]
        wins = sum(1 for p in profits if p > 0)

        htf_scores = [t.get('htf_signals', {}).get('score', 0) for t in htf_trades]

        return {
            'total_with_htf': len(htf_trades),
            'wins': wins,
            'losses': len(profits) - wins,
            'win_rate': (wins / len(profits) * 100) if profits else 0,
            'avg_profit': statistics.mean(profits),
            'avg_htf_score': statistics.mean(htf_scores) if htf_scores else 0,
        }

    def _identify_top_stacks(self, trades: List[Dict], top_n: int = 5) -> List[Dict]:
        """Identify best-performing confluence factor combinations"""
        # Group by confluence factor combinations
        stack_performance = defaultdict(lambda: {'count': 0, 'profits': [], 'wins': 0})

        for trade in trades:
            factors = tuple(sorted(trade.get('confluence_factors', [])))
            if not factors:
                continue

            profit = trade.get('profit', 0)
            stack_performance[factors]['count'] += 1
            stack_performance[factors]['profits'].append(profit)
            if profit > 0:
                stack_performance[factors]['wins'] += 1

        # Convert to list and calculate metrics
        stacks = []
        for factors, data in stack_performance.items():
            if data['count'] < 3:  # Require at least 3 trades for statistical significance
                continue

            win_rate = (data['wins'] / data['count'] * 100) if data['count'] > 0 else 0
            avg_profit = statistics.mean(data['profits']) if data['profits'] else 0

            stacks.append({
                'factors': list(factors),
                'total_trades': data['count'],
                'wins': data['wins'],
                'win_rate': win_rate,
                'avg_profit': avg_profit,
                'total_profit': sum(data['profits']),
            })

        # Sort by win rate then avg profit
        stacks.sort(key=lambda x: (x['win_rate'], x['avg_profit']), reverse=True)

        return stacks[:top_n]

    def identify_confluence_patterns(self, trades: List[Dict]) -> List[Dict]:
        """
        Identify patterns in confluence effectiveness

        Args:
            trades: List of trade records

        Returns:
            List of identified patterns
        """
        patterns = []

        if not trades:
            return patterns

        # Filter trades with confluence data
        confluence_trades = [t for t in trades if t.get('confluence_score') is not None]

        if len(confluence_trades) < 10:
            return patterns

        # Analyze score effectiveness
        score_analysis = self._analyze_by_score(confluence_trades)

        # Pattern 1: High score underperforming
        if score_analysis.get('7+', {}).get('total_trades', 0) >= 5:
            high_score_wr = score_analysis['7+']['win_rate']
            if high_score_wr < 50:
                patterns.append({
                    'type': 'high_score_underperforming',
                    'score_range': '7+',
                    'win_rate': high_score_wr,
                    'message': f"High confluence scores (7+) underperforming ({high_score_wr:.1f}% WR) - check market regime correlation",
                    'severity': 'warning',
                })

        # Pattern 2: Low score outperforming (unexpected)
        if score_analysis.get('4', {}).get('total_trades', 0) >= 5:
            low_score_wr = score_analysis['4']['win_rate']
            if low_score_wr > 70:
                patterns.append({
                    'type': 'low_score_outperforming',
                    'score_range': '4',
                    'win_rate': low_score_wr,
                    'message': f"Minimum confluence (score 4) outperforming ({low_score_wr:.1f}% WR) - signals well-tuned",
                    'severity': 'info',
                })

        # Pattern 3: Breakout vs mean reversion preference
        strategy_analysis = self._analyze_by_strategy(confluence_trades)
        breakout_wr = strategy_analysis.get('breakout', {}).get('win_rate', 0)
        mr_wr = strategy_analysis.get('mean_reversion', {}).get('win_rate', 0)

        if breakout_wr > 0 and mr_wr > 0:
            if breakout_wr > mr_wr + 20:
                patterns.append({
                    'type': 'breakout_preference',
                    'breakout_wr': breakout_wr,
                    'mean_reversion_wr': mr_wr,
                    'message': f"Breakout strategy outperforming mean reversion ({breakout_wr:.1f}% vs {mr_wr:.1f}%)",
                    'severity': 'info',
                })
            elif mr_wr > breakout_wr + 20:
                patterns.append({
                    'type': 'mean_reversion_preference',
                    'breakout_wr': breakout_wr,
                    'mean_reversion_wr': mr_wr,
                    'message': f"Mean reversion outperforming breakout ({mr_wr:.1f}% vs {breakout_wr:.1f}%)",
                    'severity': 'info',
                })

        # Pattern 4: Specific factor dominance
        factor_analysis = self._analyze_by_factor(confluence_trades)
        if factor_analysis:
            best_factor = list(factor_analysis.items())[0]
            if best_factor[1]['total_trades'] >= 5 and best_factor[1]['win_rate'] > 80:
                patterns.append({
                    'type': 'dominant_factor',
                    'factor': best_factor[0],
                    'win_rate': best_factor[1]['win_rate'],
                    'message': f"'{best_factor[0]}' factor highly effective ({best_factor[1]['win_rate']:.1f}% WR)",
                    'severity': 'info',
                })

        return patterns

    def _empty_bucket_metrics(self) -> Dict:
        """Return empty metrics for a bucket"""
        return {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
            'avg_profit': 0,
            'total_profit': 0,
        }

    def _empty_analysis(self) -> Dict:
        """Return empty analysis"""
        return {
            'by_score': {},
            'by_factor': {},
            'by_strategy': {},
            'breakout_analysis': {},
            'htf_analysis': {},
            'top_stacks': [],
        }
