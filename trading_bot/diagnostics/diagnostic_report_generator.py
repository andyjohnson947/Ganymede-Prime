"""
Diagnostic Report Generator - Deep-dive analysis of trading performance

Analyzes last X days of trading to answer:
- What's working? (Keep doing this)
- What's broken? (Fix or remove this)
- What needs tuning? (Adjust parameters)
- Is regime detection accurate?
- Which confluence factors actually work?
- Are recovery mechanisms effective?

Usage:
    from diagnostics.diagnostic_report_generator import DiagnosticReportGenerator

    generator = DiagnosticReportGenerator(mt5_manager, data_store)
    report = generator.generate_report(days=7)
    generator.print_report(report)
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import statistics
from pathlib import Path


class DiagnosticReportGenerator:
    """Generates comprehensive diagnostic reports"""

    def __init__(self, mt5_manager, data_store):
        """
        Initialize report generator

        Args:
            mt5_manager: MT5Manager instance for price data
            data_store: DataStore instance for diagnostic history
        """
        self.mt5 = mt5_manager
        self.data_store = data_store

    def generate_report(
        self,
        days: int = 7,
        min_trades: int = 5
    ) -> Dict:
        """
        Generate comprehensive diagnostic report

        Args:
            days: Number of days to analyze
            min_trades: Minimum trades required for statistical significance

        Returns:
            Dict containing full analysis
        """
        print(f"\n{'='*80}")
        print(f"📊 DIAGNOSTIC REPORT GENERATOR")
        print(f"{'='*80}")
        print(f"Analyzing last {days} days of trading...\n")

        report = {
            'period': days,
            'generated_at': datetime.now().isoformat(),
            'min_trades_threshold': min_trades,
        }

        # 1. Get historical data
        print("📥 Loading historical data...")
        trades = self.data_store.get_trades(days=days)
        market_conditions = self.data_store.get_market_conditions(hours=days*24)
        recovery_actions = self.data_store.get_recovery_actions(days=days)

        report['total_trades'] = len(trades)
        report['total_market_snapshots'] = len(market_conditions)
        report['total_recovery_actions'] = len(recovery_actions)

        print(f"   ✅ Loaded {len(trades)} trades")
        print(f"   ✅ Loaded {len(market_conditions)} market snapshots")
        print(f"   ✅ Loaded {len(recovery_actions)} recovery actions\n")

        if len(trades) < min_trades:
            report['insufficient_data'] = True
            report['message'] = f"Need at least {min_trades} trades for analysis (found {len(trades)})"
            return report

        # 2. Analyze regime detection accuracy
        print("🎯 Analyzing regime detection accuracy...")
        report['regime_analysis'] = self._analyze_regime_accuracy(
            trades, market_conditions, recovery_actions
        )

        # 3. Analyze confluence effectiveness
        print("🔍 Analyzing confluence factor effectiveness...")
        report['confluence_analysis'] = self._analyze_confluence_effectiveness(trades)

        # 4. Analyze recovery mechanisms
        print("🔧 Analyzing recovery mechanism performance...")
        report['recovery_analysis'] = self._analyze_recovery_performance(
            recovery_actions, trades
        )

        # 5. Analyze strategy performance
        print("📈 Analyzing strategy mode performance...")
        report['strategy_analysis'] = self._analyze_strategy_performance(trades)

        # 6. Generate recommendations
        print("💡 Generating actionable recommendations...\n")
        report['recommendations'] = self._generate_recommendations(report)

        return report

    def _analyze_regime_accuracy(
        self,
        trades: List[Dict],
        market_conditions: List[Dict],
        recovery_actions: List[Dict]
    ) -> Dict:
        """
        Analyze how accurate Hurst + VHF regime detection is

        Key questions:
        - Did trades in "RANGING" regime actually win?
        - Did trades in "TRENDING" regime actually lose?
        - Were recovery blocks justified?
        - False positives/negatives?
        """
        analysis = {
            'ranging_trades': [],
            'trending_trades': [],
            'transitional_trades': [],
            'recovery_blocks': {
                'justified': 0,  # Block saved us from loss
                'false_positive': 0,  # Block prevented potential win
                'total': 0
            }
        }

        # Categorize trades by regime at entry
        for trade in trades:
            # Find market condition near trade entry time
            entry_time = trade.get('open_time')
            if not entry_time:
                continue

            # Find closest market snapshot
            closest_condition = self._find_closest_condition(entry_time, market_conditions)
            if not closest_condition:
                continue

            regime = closest_condition.get('advanced_regime', 'unknown')
            hurst = closest_condition.get('hurst_exponent')
            vhf = closest_condition.get('vhf')
            recovery_safe = closest_condition.get('recovery_safe', False)

            trade_info = {
                'ticket': trade.get('ticket'),
                'profit': trade.get('profit', 0),
                'symbol': trade.get('symbol'),
                'regime': regime,
                'hurst': hurst,
                'vhf': vhf,
                'recovery_safe': recovery_safe,
                'win': trade.get('profit', 0) > 0
            }

            if regime == 'ranging':
                analysis['ranging_trades'].append(trade_info)
            elif regime == 'trending':
                analysis['trending_trades'].append(trade_info)
            else:
                analysis['transitional_trades'].append(trade_info)

        # Calculate accuracy metrics
        if analysis['ranging_trades']:
            ranging_wins = sum(1 for t in analysis['ranging_trades'] if t['win'])
            analysis['ranging_win_rate'] = ranging_wins / len(analysis['ranging_trades']) * 100
            analysis['ranging_total'] = len(analysis['ranging_trades'])
        else:
            analysis['ranging_win_rate'] = 0
            analysis['ranging_total'] = 0

        if analysis['trending_trades']:
            trending_wins = sum(1 for t in analysis['trending_trades'] if t['win'])
            analysis['trending_win_rate'] = trending_wins / len(analysis['trending_trades']) * 100
            analysis['trending_total'] = len(analysis['trending_trades'])
        else:
            analysis['trending_win_rate'] = 0
            analysis['trending_total'] = 0

        # Analyze recovery blocks
        for action in recovery_actions:
            if action.get('type') == 'blocked':
                analysis['recovery_blocks']['total'] += 1

                # Check if the block was justified (position eventually lost money)
                ticket = action.get('ticket')
                trade = next((t for t in trades if t.get('ticket') == ticket), None)

                if trade:
                    if trade.get('profit', 0) < 0:
                        analysis['recovery_blocks']['justified'] += 1
                    else:
                        analysis['recovery_blocks']['false_positive'] += 1

        # Calculate block accuracy
        total_blocks = analysis['recovery_blocks']['total']
        if total_blocks > 0:
            justified_rate = analysis['recovery_blocks']['justified'] / total_blocks * 100
            analysis['recovery_blocks']['justified_rate'] = justified_rate
        else:
            analysis['recovery_blocks']['justified_rate'] = 0

        # Verdict
        analysis['verdict'] = self._regime_verdict(analysis)

        return analysis

    def _analyze_confluence_effectiveness(self, trades: List[Dict]) -> Dict:
        """
        Analyze which confluence factors actually work

        Key questions:
        - Which factors correlate with wins?
        - Which factors correlate with losses?
        - Are high scores actually better?
        - Should any factors be removed?
        """
        analysis = {
            'by_factor': {},
            'by_score': {},
            'factor_correlations': {},
            'verdict': {}
        }

        # Only analyze trades with confluence data
        confluence_trades = [t for t in trades if t.get('confluence_score') is not None]

        if not confluence_trades:
            analysis['verdict']['status'] = 'no_data'
            analysis['verdict']['message'] = "No confluence data available"
            return analysis

        # Analyze by individual factor
        factor_performance = defaultdict(lambda: {'wins': 0, 'losses': 0, 'profits': []})

        for trade in confluence_trades:
            factors = trade.get('confluence_factors', [])
            profit = trade.get('profit', 0)
            is_win = profit > 0

            for factor in factors:
                factor_performance[factor]['profits'].append(profit)
                if is_win:
                    factor_performance[factor]['wins'] += 1
                else:
                    factor_performance[factor]['losses'] += 1

        # Calculate metrics for each factor
        for factor, data in factor_performance.items():
            total = data['wins'] + data['losses']
            if total >= 3:  # Minimum sample size
                win_rate = data['wins'] / total * 100
                avg_profit = statistics.mean(data['profits']) if data['profits'] else 0

                analysis['by_factor'][factor] = {
                    'total_trades': total,
                    'wins': data['wins'],
                    'losses': data['losses'],
                    'win_rate': win_rate,
                    'avg_profit': avg_profit,
                    'total_profit': sum(data['profits']),
                    'verdict': self._factor_verdict(win_rate, total)
                }

        # Sort by win rate
        analysis['by_factor'] = dict(
            sorted(analysis['by_factor'].items(), key=lambda x: x[1]['win_rate'], reverse=True)
        )

        # Analyze by score
        score_buckets = defaultdict(lambda: {'wins': 0, 'losses': 0, 'profits': []})

        for trade in confluence_trades:
            score = trade.get('confluence_score', 0)
            profit = trade.get('profit', 0)

            # Bucket scores
            if score <= 4:
                bucket = '4-'
            elif score == 5:
                bucket = '5'
            elif score == 6:
                bucket = '6'
            else:
                bucket = '7+'

            score_buckets[bucket]['profits'].append(profit)
            if profit > 0:
                score_buckets[bucket]['wins'] += 1
            else:
                score_buckets[bucket]['losses'] += 1

        # Calculate metrics for each score bucket
        for bucket, data in score_buckets.items():
            total = data['wins'] + data['losses']
            if total > 0:
                win_rate = data['wins'] / total * 100
                avg_profit = statistics.mean(data['profits']) if data['profits'] else 0

                analysis['by_score'][bucket] = {
                    'total_trades': total,
                    'wins': data['wins'],
                    'losses': data['losses'],
                    'win_rate': win_rate,
                    'avg_profit': avg_profit,
                    'total_profit': sum(data['profits'])
                }

        # Overall verdict
        analysis['verdict'] = self._confluence_verdict(analysis)

        return analysis

    def _analyze_recovery_performance(
        self,
        recovery_actions: List[Dict],
        trades: List[Dict]
    ) -> Dict:
        """
        Analyze recovery mechanism effectiveness

        Key questions:
        - Grid: Does it help or hurt?
        - Hedge: Worth the risk?
        - DCA: Effective or just digging deeper?
        - Should any be disabled?
        """
        analysis = {
            'grid': {'triggered': 0, 'saved': 0, 'failed': 0, 'profits': []},
            'hedge': {'triggered': 0, 'saved': 0, 'failed': 0, 'profits': []},
            'dca': {'triggered': 0, 'saved': 0, 'failed': 0, 'profits': []},
            'verdict': {}
        }

        # Group recovery actions by ticket
        actions_by_ticket = defaultdict(list)
        for action in recovery_actions:
            ticket = action.get('ticket')
            if ticket:
                actions_by_ticket[ticket].append(action)

        # Analyze each recovered trade
        for ticket, actions in actions_by_ticket.items():
            # Find final trade outcome
            trade = next((t for t in trades if t.get('ticket') == ticket), None)
            if not trade:
                continue

            profit = trade.get('profit', 0)
            was_saved = profit > 0  # Recovery turned loss into profit

            # Check which recovery types were used
            recovery_types = set()
            for action in actions:
                rec_type = action.get('recovery_type', '').lower()
                if rec_type in ['grid', 'hedge', 'dca']:
                    recovery_types.add(rec_type)

            # Record results for each recovery type used
            for rec_type in recovery_types:
                analysis[rec_type]['triggered'] += 1
                analysis[rec_type]['profits'].append(profit)

                if was_saved:
                    analysis[rec_type]['saved'] += 1
                else:
                    analysis[rec_type]['failed'] += 1

        # Calculate metrics
        for rec_type in ['grid', 'hedge', 'dca']:
            data = analysis[rec_type]
            if data['triggered'] > 0:
                data['success_rate'] = data['saved'] / data['triggered'] * 100
                data['avg_profit'] = statistics.mean(data['profits']) if data['profits'] else 0
                data['total_profit'] = sum(data['profits'])
                data['verdict'] = self._recovery_verdict(data['success_rate'], data['triggered'])
            else:
                data['success_rate'] = 0
                data['avg_profit'] = 0
                data['total_profit'] = 0
                data['verdict'] = 'not_used'

        # Overall verdict
        analysis['verdict'] = self._overall_recovery_verdict(analysis)

        return analysis

    def _analyze_strategy_performance(self, trades: List[Dict]) -> Dict:
        """
        Analyze strategy mode performance

        Key questions:
        - Breakout vs Mean Reversion: which works better?
        - Should one be disabled?
        - Are they being used in right conditions?
        """
        analysis = {
            'breakout': {'wins': 0, 'losses': 0, 'profits': []},
            'mean_reversion': {'wins': 0, 'losses': 0, 'profits': []},
            'unknown': {'wins': 0, 'losses': 0, 'profits': []},
            'verdict': {}
        }

        for trade in trades:
            strategy = trade.get('strategy_mode', 'unknown')
            profit = trade.get('profit', 0)

            if strategy not in analysis:
                strategy = 'unknown'

            analysis[strategy]['profits'].append(profit)
            if profit > 0:
                analysis[strategy]['wins'] += 1
            else:
                analysis[strategy]['losses'] += 1

        # Calculate metrics
        for strategy in ['breakout', 'mean_reversion', 'unknown']:
            data = analysis[strategy]
            total = data['wins'] + data['losses']

            if total > 0:
                data['total_trades'] = total
                data['win_rate'] = data['wins'] / total * 100
                data['avg_profit'] = statistics.mean(data['profits']) if data['profits'] else 0
                data['total_profit'] = sum(data['profits'])
            else:
                data['total_trades'] = 0
                data['win_rate'] = 0
                data['avg_profit'] = 0
                data['total_profit'] = 0

        # Verdict
        analysis['verdict'] = self._strategy_verdict(analysis)

        return analysis

    def _find_closest_condition(
        self,
        target_time: str,
        conditions: List[Dict]
    ) -> Optional[Dict]:
        """Find market condition closest to target time"""
        try:
            target_dt = datetime.fromisoformat(target_time.replace('Z', '+00:00'))
        except:
            return None

        closest = None
        min_diff = None

        for condition in conditions:
            try:
                cond_time = condition.get('timestamp')
                cond_dt = datetime.fromisoformat(cond_time.replace('Z', '+00:00'))
                diff = abs((target_dt - cond_dt).total_seconds())

                if min_diff is None or diff < min_diff:
                    min_diff = diff
                    closest = condition
            except:
                continue

        return closest

    def _regime_verdict(self, analysis: Dict) -> Dict:
        """Generate verdict for regime detection"""
        verdict = {}

        ranging_wr = analysis.get('ranging_win_rate', 0)
        trending_wr = analysis.get('trending_win_rate', 0)
        ranging_total = analysis.get('ranging_total', 0)
        trending_total = analysis.get('trending_total', 0)

        # Check if regime detection is working as expected
        if ranging_total >= 5:
            if ranging_wr >= 65:
                verdict['ranging'] = 'EXCELLENT - Ranging regime detection is accurate'
            elif ranging_wr >= 55:
                verdict['ranging'] = 'GOOD - Ranging detection working well'
            else:
                verdict['ranging'] = 'POOR - Ranging trades underperforming (check if false positives)'
        else:
            verdict['ranging'] = 'INSUFFICIENT DATA'

        if trending_total >= 5:
            if trending_wr <= 40:
                verdict['trending'] = 'EXCELLENT - Correctly avoiding trending markets'
            elif trending_wr <= 55:
                verdict['trending'] = 'ACCEPTABLE - Some trending trades still winning'
            else:
                verdict['trending'] = 'WARNING - Trending trades winning too often (detector may be too conservative)'
        else:
            verdict['trending'] = 'INSUFFICIENT DATA'

        # Check recovery block accuracy
        block_accuracy = analysis['recovery_blocks'].get('justified_rate', 0)
        total_blocks = analysis['recovery_blocks'].get('total', 0)

        if total_blocks >= 3:
            if block_accuracy >= 70:
                verdict['blocks'] = 'EXCELLENT - Blocks are preventing losses'
            elif block_accuracy >= 50:
                verdict['blocks'] = 'ACCEPTABLE - Most blocks justified'
            else:
                verdict['blocks'] = 'POOR - Too many false positive blocks (losing opportunities)'
        else:
            verdict['blocks'] = 'INSUFFICIENT DATA'

        return verdict

    def _factor_verdict(self, win_rate: float, sample_size: int) -> str:
        """Generate verdict for individual confluence factor"""
        if sample_size < 3:
            return 'INSUFFICIENT_DATA'
        elif win_rate >= 75:
            return 'EXCELLENT - Keep this factor'
        elif win_rate >= 60:
            return 'GOOD - Factor is helping'
        elif win_rate >= 45:
            return 'NEUTRAL - Factor not adding much value'
        else:
            return 'POOR - Consider removing this factor'

    def _confluence_verdict(self, analysis: Dict) -> Dict:
        """Generate overall confluence verdict"""
        verdict = {}

        by_factor = analysis.get('by_factor', {})
        by_score = analysis.get('by_score', {})

        # Identify best and worst factors
        if by_factor:
            factors_sorted = sorted(by_factor.items(), key=lambda x: x[1]['win_rate'], reverse=True)

            if factors_sorted:
                best_factor = factors_sorted[0]
                worst_factor = factors_sorted[-1]

                verdict['best_factor'] = {
                    'name': best_factor[0],
                    'win_rate': best_factor[1]['win_rate'],
                    'message': f"'{best_factor[0]}' is your best factor ({best_factor[1]['win_rate']:.1f}% WR)"
                }

                if worst_factor[1]['win_rate'] < 45 and worst_factor[1]['total_trades'] >= 5:
                    verdict['worst_factor'] = {
                        'name': worst_factor[0],
                        'win_rate': worst_factor[1]['win_rate'],
                        'message': f"'{worst_factor[0]}' is dragging down performance ({worst_factor[1]['win_rate']:.1f}% WR) - CONSIDER REMOVING"
                    }

        # Check if higher scores actually perform better
        if by_score:
            score_trend = []
            for bucket in ['4-', '5', '6', '7+']:
                if bucket in by_score:
                    score_trend.append((bucket, by_score[bucket]['win_rate']))

            if len(score_trend) >= 3:
                # Check if win rate increases with score
                rates = [wr for _, wr in score_trend]
                is_increasing = all(rates[i] <= rates[i+1] for i in range(len(rates)-1))
                is_decreasing = all(rates[i] >= rates[i+1] for i in range(len(rates)-1))

                if is_increasing:
                    verdict['score_correlation'] = 'EXCELLENT - Higher scores perform better (system working as designed)'
                elif is_decreasing:
                    verdict['score_correlation'] = 'INVERTED - Lower scores performing better (investigate signal logic)'
                else:
                    verdict['score_correlation'] = 'MIXED - No clear correlation between score and performance'

        return verdict

    def _recovery_verdict(self, success_rate: float, sample_size: int) -> str:
        """Generate verdict for recovery mechanism"""
        if sample_size < 3:
            return 'INSUFFICIENT_DATA'
        elif success_rate >= 70:
            return 'EXCELLENT - Highly effective'
        elif success_rate >= 55:
            return 'GOOD - Worth keeping'
        elif success_rate >= 40:
            return 'MARGINAL - Consider tuning parameters'
        else:
            return 'POOR - Consider disabling'

    def _overall_recovery_verdict(self, analysis: Dict) -> Dict:
        """Generate overall recovery verdict"""
        verdict = {}

        for rec_type in ['grid', 'hedge', 'dca']:
            data = analysis[rec_type]
            if data.get('verdict') == 'POOR':
                verdict[rec_type] = f"DISABLE - {rec_type.upper()} is not effective"
            elif data.get('verdict') == 'MARGINAL':
                verdict[rec_type] = f"TUNE - {rec_type.upper()} needs parameter adjustment"
            elif data.get('verdict') in ['GOOD', 'EXCELLENT']:
                verdict[rec_type] = f"KEEP - {rec_type.upper()} is working well"

        return verdict

    def _strategy_verdict(self, analysis: Dict) -> Dict:
        """Generate strategy mode verdict"""
        verdict = {}

        breakout_data = analysis.get('breakout', {})
        mr_data = analysis.get('mean_reversion', {})

        breakout_wr = breakout_data.get('win_rate', 0)
        mr_wr = mr_data.get('win_rate', 0)
        breakout_total = breakout_data.get('total_trades', 0)
        mr_total = mr_data.get('total_trades', 0)

        # Analyze breakout strategy
        if breakout_total >= 5:
            if breakout_wr >= 70:
                verdict['breakout'] = 'EXCELLENT - Breakout strategy is highly effective'
            elif breakout_wr >= 55:
                verdict['breakout'] = 'GOOD - Breakout strategy working well'
            elif breakout_wr >= 40:
                verdict['breakout'] = 'MARGINAL - Breakout needs improvement'
            else:
                verdict['breakout'] = 'POOR - Consider disabling breakout strategy'
        else:
            verdict['breakout'] = 'INSUFFICIENT DATA'

        # Analyze mean reversion strategy
        if mr_total >= 5:
            if mr_wr >= 70:
                verdict['mean_reversion'] = 'EXCELLENT - Mean reversion is highly effective'
            elif mr_wr >= 55:
                verdict['mean_reversion'] = 'GOOD - Mean reversion working well'
            elif mr_wr >= 40:
                verdict['mean_reversion'] = 'MARGINAL - Mean reversion needs improvement'
            else:
                verdict['mean_reversion'] = 'POOR - Consider disabling mean reversion'
        else:
            verdict['mean_reversion'] = 'INSUFFICIENT DATA'

        # Compare strategies
        if breakout_total >= 5 and mr_total >= 5:
            diff = abs(breakout_wr - mr_wr)
            if diff > 20:
                if breakout_wr > mr_wr:
                    verdict['comparison'] = f'Breakout outperforming Mean Reversion by {diff:.1f}% - Consider focusing on breakouts'
                else:
                    verdict['comparison'] = f'Mean Reversion outperforming Breakout by {diff:.1f}% - Consider focusing on mean reversion'
            else:
                verdict['comparison'] = 'Both strategies performing similarly - keep both active'

        return verdict

    def _generate_recommendations(self, report: Dict) -> List[Dict]:
        """Generate actionable recommendations from analysis"""
        recommendations = []

        # Regime detection recommendations
        regime = report.get('regime_analysis', {}).get('verdict', {})
        if 'POOR' in str(regime.get('ranging', '')):
            recommendations.append({
                'priority': 'HIGH',
                'category': 'REGIME',
                'action': 'FIX',
                'message': 'Ranging regime detection may have false positives - review Hurst/VHF thresholds'
            })

        if 'WARNING' in str(regime.get('trending', '')):
            recommendations.append({
                'priority': 'MEDIUM',
                'category': 'REGIME',
                'action': 'TUNE',
                'message': 'Trending detector may be too conservative - some trending trades are winning'
            })

        if 'POOR' in str(regime.get('blocks', '')):
            recommendations.append({
                'priority': 'HIGH',
                'category': 'REGIME',
                'action': 'FIX',
                'message': 'Recovery blocks have too many false positives - losing trading opportunities'
            })

        # Confluence recommendations
        confluence = report.get('confluence_analysis', {})
        worst_factor = confluence.get('verdict', {}).get('worst_factor')
        if worst_factor:
            recommendations.append({
                'priority': 'MEDIUM',
                'category': 'CONFLUENCE',
                'action': 'REMOVE',
                'message': f"Remove '{worst_factor['name']}' factor - only {worst_factor['win_rate']:.1f}% WR"
            })

        if 'INVERTED' in str(confluence.get('verdict', {}).get('score_correlation', '')):
            recommendations.append({
                'priority': 'HIGH',
                'category': 'CONFLUENCE',
                'action': 'FIX',
                'message': 'Lower confluence scores performing better than high scores - signal logic may be inverted'
            })

        # Recovery recommendations
        recovery = report.get('recovery_analysis', {}).get('verdict', {})
        for rec_type, verdict in recovery.items():
            if 'DISABLE' in verdict:
                recommendations.append({
                    'priority': 'HIGH',
                    'category': 'RECOVERY',
                    'action': 'REMOVE',
                    'message': f"Disable {rec_type.upper()} - not effective in current market conditions"
                })
            elif 'TUNE' in verdict:
                recommendations.append({
                    'priority': 'MEDIUM',
                    'category': 'RECOVERY',
                    'action': 'TUNE',
                    'message': f"Adjust {rec_type.upper()} parameters - marginal performance"
                })

        # Strategy recommendations
        strategy = report.get('strategy_analysis', {}).get('verdict', {})
        if 'POOR' in str(strategy.get('breakout', '')):
            recommendations.append({
                'priority': 'HIGH',
                'category': 'STRATEGY',
                'action': 'REMOVE',
                'message': 'Disable breakout strategy - consistently underperforming'
            })

        if 'POOR' in str(strategy.get('mean_reversion', '')):
            recommendations.append({
                'priority': 'HIGH',
                'category': 'STRATEGY',
                'action': 'REMOVE',
                'message': 'Disable mean reversion strategy - consistently underperforming'
            })

        # Sort by priority
        priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 3))

        return recommendations

    def print_report(self, report: Dict):
        """Print formatted report"""
        print(f"\n{'='*80}")
        print(f"📊 DIAGNOSTIC REPORT")
        print(f"{'='*80}")
        print(f"Period: Last {report['period']} days")
        print(f"Generated: {report['generated_at']}")
        print(f"Total Trades: {report['total_trades']}")
        print(f"{'='*80}\n")

        if report.get('insufficient_data'):
            print(f"⚠️  {report['message']}\n")
            return

        # 1. Regime Detection Analysis
        print(f"🎯 REGIME DETECTION ACCURACY")
        print(f"{'─'*80}")
        regime = report['regime_analysis']

        print(f"\nRanging Market Performance:")
        print(f"   Total trades: {regime['ranging_total']}")
        print(f"   Win rate: {regime['ranging_win_rate']:.1f}%")
        print(f"   Verdict: {regime['verdict'].get('ranging', 'N/A')}")

        print(f"\nTrending Market Performance:")
        print(f"   Total trades: {regime['trending_total']}")
        print(f"   Win rate: {regime['trending_win_rate']:.1f}%")
        print(f"   Verdict: {regime['verdict'].get('trending', 'N/A')}")

        print(f"\nRecovery Blocks:")
        blocks = regime['recovery_blocks']
        print(f"   Total blocks: {blocks['total']}")
        print(f"   Justified: {blocks['justified']} ({blocks.get('justified_rate', 0):.1f}%)")
        print(f"   False positives: {blocks['false_positive']}")
        print(f"   Verdict: {regime['verdict'].get('blocks', 'N/A')}")

        # 2. Confluence Analysis
        print(f"\n🔍 CONFLUENCE EFFECTIVENESS")
        print(f"{'─'*80}")
        confluence = report['confluence_analysis']

        print(f"\nBy Factor:")
        by_factor = confluence.get('by_factor', {})
        for factor, data in list(by_factor.items())[:10]:  # Top 10
            status = '✅' if data['win_rate'] >= 60 else '⚠️' if data['win_rate'] >= 45 else '❌'
            print(f"   {status} {factor}: {data['win_rate']:.1f}% WR ({data['total_trades']} trades) - {data['verdict']}")

        print(f"\nBy Score:")
        by_score = confluence.get('by_score', {})
        for bucket in ['4-', '5', '6', '7+']:
            if bucket in by_score:
                data = by_score[bucket]
                print(f"   Score {bucket}: {data['win_rate']:.1f}% WR ({data['total_trades']} trades, ${data['total_profit']:.2f})")

        verdict = confluence.get('verdict', {})
        if 'best_factor' in verdict:
            print(f"\n✨ {verdict['best_factor']['message']}")
        if 'worst_factor' in verdict:
            print(f"⚠️  {verdict['worst_factor']['message']}")
        if 'score_correlation' in verdict:
            print(f"📊 {verdict['score_correlation']}")

        # 3. Recovery Performance
        print(f"\n🔧 RECOVERY MECHANISMS")
        print(f"{'─'*80}")
        recovery = report['recovery_analysis']

        for rec_type in ['grid', 'hedge', 'dca']:
            data = recovery[rec_type]
            if data['triggered'] > 0:
                status = '✅' if data['success_rate'] >= 55 else '⚠️' if data['success_rate'] >= 40 else '❌'
                print(f"\n   {status} {rec_type.upper()}:")
                print(f"      Triggered: {data['triggered']} times")
                print(f"      Success rate: {data['success_rate']:.1f}%")
                print(f"      Avg profit: ${data['avg_profit']:.2f}")
                print(f"      Total profit: ${data['total_profit']:.2f}")
                print(f"      Verdict: {data['verdict']}")

        # 4. Strategy Performance
        print(f"\n📈 STRATEGY MODE PERFORMANCE")
        print(f"{'─'*80}")
        strategy = report['strategy_analysis']

        for mode in ['breakout', 'mean_reversion']:
            data = strategy[mode]
            if data['total_trades'] > 0:
                status = '✅' if data['win_rate'] >= 55 else '⚠️' if data['win_rate'] >= 40 else '❌'
                print(f"\n   {status} {mode.upper().replace('_', ' ')}:")
                print(f"      Total trades: {data['total_trades']}")
                print(f"      Win rate: {data['win_rate']:.1f}%")
                print(f"      Avg profit: ${data['avg_profit']:.2f}")
                print(f"      Total profit: ${data['total_profit']:.2f}")

        verdict = strategy.get('verdict', {})
        if 'comparison' in verdict:
            print(f"\n   📊 {verdict['comparison']}")

        # 5. Recommendations
        print(f"\n💡 ACTIONABLE RECOMMENDATIONS")
        print(f"{'─'*80}")
        recommendations = report['recommendations']

        if not recommendations:
            print("   ✅ No critical issues found - system performing well")
        else:
            for i, rec in enumerate(recommendations, 1):
                icon = '🔴' if rec['priority'] == 'HIGH' else '🟡' if rec['priority'] == 'MEDIUM' else '🟢'
                print(f"\n   {icon} [{rec['priority']}] {rec['category']} - {rec['action']}")
                print(f"      {rec['message']}")

        print(f"\n{'='*80}\n")
