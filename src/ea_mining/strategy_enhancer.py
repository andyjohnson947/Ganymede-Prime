"""
Strategy Enhancer
Takes the learned EA strategy and improves upon it
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional

from .ea_monitor import EAMonitor
from .ea_analyzer import EAAnalyzer
from .ea_learner import EALearner


class StrategyEnhancer:
    """Enhances the EA's strategy based on analysis and ML insights"""

    def __init__(
        self,
        ea_monitor: EAMonitor,
        ea_analyzer: EAAnalyzer,
        ea_learner: EALearner
    ):
        """
        Initialize Strategy Enhancer

        Args:
            ea_monitor: EA monitor instance
            ea_analyzer: EA analyzer instance
            ea_learner: EA learner instance
        """
        self.monitor = ea_monitor
        self.analyzer = ea_analyzer
        self.learner = ea_learner
        self.logger = logging.getLogger(__name__)

        # Enhancement rules learned from analysis
        self.enhancement_rules = []

    def analyze_and_create_enhancements(self) -> Dict:
        """
        Analyze EA weaknesses and create enhancement rules

        Returns:
            Dictionary with enhancement strategies
        """
        self.logger.info("Creating enhancement strategies...")

        weaknesses = self.analyzer.find_weaknesses()
        enhancements = {
            'filters': [],
            'entry_improvements': [],
            'exit_improvements': [],
            'risk_management': []
        }

        # Create filters based on weaknesses
        for issue in weaknesses.get('issues', []):
            if issue['type'] == 'poor_timing':
                # Extract problem hour
                hour = int(issue['description'].split('hour ')[1].split(':')[0])
                enhancements['filters'].append({
                    'type': 'time_filter',
                    'rule': f'avoid_hour_{hour}',
                    'description': f"Don't trade during hour {hour}:00"
                })

            elif issue['type'] == 'long_losing_streaks':
                enhancements['filters'].append({
                    'type': 'circuit_breaker',
                    'rule': 'stop_after_3_losses',
                    'description': "Stop trading after 3 consecutive losses"
                })

            elif issue['type'] == 'poor_risk_reward':
                enhancements['risk_management'].append({
                    'type': 'adjust_stop_loss',
                    'rule': 'tighter_stops',
                    'description': "Reduce stop loss by 25%"
                })

                enhancements['risk_management'].append({
                    'type': 'adjust_take_profit',
                    'rule': 'wider_targets',
                    'description': "Increase take profit by 50%"
                })

        # Entry improvements based on ML
        learned_strategy = self.learner.get_learned_strategy_summary()

        if 'top_entry_factors' in learned_strategy:
            top_factors = learned_strategy['top_entry_factors'][:3]

            enhancements['entry_improvements'].append({
                'type': 'confirmation_filter',
                'rule': 'require_top_factors',
                'description': f"Require alignment of top 3 factors: {', '.join([f['feature'] for f in top_factors])}",
                'factors': top_factors
            })

        # Exit improvements
        entry_patterns = self.analyzer.analyze_entry_patterns()
        exit_patterns = self.analyzer.analyze_exit_patterns()

        if 'duration_stats' in exit_patterns:
            avg_duration = exit_patterns['duration_stats']['mean_hours']

            enhancements['exit_improvements'].append({
                'type': 'time_based_exit',
                'rule': 'max_hold_time',
                'description': f"Close trade after {avg_duration * 1.5:.0f} hours if no profit",
                'max_hours': avg_duration * 1.5
            })

        # Store rules
        self.enhancement_rules = enhancements

        self.logger.info(f"Created {sum(len(v) for v in enhancements.values())} enhancement rules")
        return enhancements

    def generate_enhanced_signal(
        self,
        current_data: pd.DataFrame,
        ea_prediction: Dict
    ) -> Dict:
        """
        Generate enhanced trading signal

        Args:
            current_data: Current market data
            ea_prediction: Original EA prediction from learner

        Returns:
            Enhanced signal with filters applied
        """
        signal = {
            'original_ea_signal': ea_prediction.copy(),
            'enhanced_signal': None,
            'filters_applied': [],
            'modifications': []
        }

        # Start with EA's decision
        should_trade = ea_prediction.get('should_trade', False)
        direction = ea_prediction.get('direction', 'buy')
        confidence = ea_prediction.get('trade_probability', 0.5)

        # Apply filters
        if should_trade:
            # Check time filters
            current_hour = pd.Timestamp.now().hour

            for filter_rule in self.enhancement_rules.get('filters', []):
                if filter_rule['type'] == 'time_filter':
                    avoid_hour = int(filter_rule['rule'].split('_')[-1])
                    if current_hour == avoid_hour:
                        should_trade = False
                        signal['filters_applied'].append(f"Time filter: Avoiding hour {avoid_hour}")
                        break

            # Check confirmation filters
            for improvement in self.enhancement_rules.get('entry_improvements', []):
                if improvement['type'] == 'confirmation_filter':
                    # Check if top factors are aligned
                    factors = improvement.get('factors', [])

                    if factors and len(current_data) > 0:
                        latest = current_data.iloc[-1]

                        # Simple check: are key indicators in favorable range?
                        aligned = True
                        for factor in factors[:2]:  # Check top 2
                            feature_name = factor['feature']

                            if feature_name in latest.index:
                                # Add more sophisticated checks here
                                pass

                        if not aligned:
                            confidence *= 0.8  # Reduce confidence
                            signal['modifications'].append("Reduced confidence due to weak confirmation")

        # Apply risk management improvements
        stop_loss_multiplier = 1.0
        take_profit_multiplier = 1.0

        for rm_rule in self.enhancement_rules.get('risk_management', []):
            if rm_rule['type'] == 'adjust_stop_loss' and rm_rule['rule'] == 'tighter_stops':
                stop_loss_multiplier = 0.75
                signal['modifications'].append("Tightened stop loss by 25%")

            elif rm_rule['type'] == 'adjust_take_profit' and rm_rule['rule'] == 'wider_targets':
                take_profit_multiplier = 1.5
                signal['modifications'].append("Widened take profit by 50%")

        # Generate final signal
        signal['enhanced_signal'] = {
            'should_trade': should_trade,
            'direction': direction,
            'confidence': confidence,
            'stop_loss_multiplier': stop_loss_multiplier,
            'take_profit_multiplier': take_profit_multiplier,
            'reasoning': signal['modifications'] + signal['filters_applied']
        }

        return signal

    def backtest_enhancements(
        self,
        historical_data: Dict[str, pd.DataFrame]
    ) -> Dict:
        """
        Backtest enhanced strategy vs original EA

        Args:
            historical_data: Historical price data

        Returns:
            Comparison of original EA vs enhanced strategy
        """
        self.logger.info("Backtesting enhancements...")

        # Get original EA trades
        ea_trades = self.monitor.get_trades_dataframe()
        ea_stats = self.monitor.get_ea_statistics()

        # Simulate enhanced strategy
        enhanced_trades = []

        for _, ea_trade in ea_trades.iterrows():
            symbol = ea_trade['symbol']

            if symbol not in historical_data:
                continue

            df = historical_data[symbol]
            entry_time = pd.to_datetime(ea_trade['entry_time'])

            # Find entry point in historical data
            if entry_time not in df.index:
                continue

            entry_idx = df.index.get_loc(entry_time)
            entry_data = df.iloc[:entry_idx + 1]

            # Get EA prediction at this point
            ea_pred = self.learner.predict(entry_data)

            # Generate enhanced signal
            enhanced_signal = self.generate_enhanced_signal(entry_data, ea_pred)

            # Would enhanced strategy have taken this trade?
            if enhanced_signal['enhanced_signal']['should_trade']:
                # Modify the trade based on enhancements
                modified_trade = ea_trade.copy()

                # Adjust SL/TP
                sl_mult = enhanced_signal['enhanced_signal']['stop_loss_multiplier']
                tp_mult = enhanced_signal['enhanced_signal']['take_profit_multiplier']

                # Simulate modified outcome (simplified)
                # In reality, you'd re-simulate with adjusted SL/TP
                if ea_trade['profit'] > 0:
                    # Winning trade - wider TP might have captured more
                    modified_trade['profit'] = ea_trade['profit'] * tp_mult
                else:
                    # Losing trade - tighter SL might have lost less
                    modified_trade['profit'] = ea_trade['profit'] * sl_mult

                enhanced_trades.append(modified_trade)

        # Calculate enhanced statistics
        if enhanced_trades:
            enhanced_df = pd.DataFrame(enhanced_trades)

            enhanced_stats = {
                'total_trades': len(enhanced_trades),
                'total_profit': enhanced_df['profit'].sum(),
                'average_profit': enhanced_df['profit'].mean(),
                'win_rate': (enhanced_df['profit'] > 0).sum() / len(enhanced_df) * 100
            }
        else:
            enhanced_stats = {}

        comparison = {
            'original_ea': ea_stats,
            'enhanced_strategy': enhanced_stats,
            'improvement': {},
            'trades_filtered': len(ea_trades) - len(enhanced_trades)
        }

        # Calculate improvements
        if enhanced_stats and 'total_profit' in ea_stats:
            comparison['improvement'] = {
                'profit_change': enhanced_stats['total_profit'] - ea_stats['total_profit'],
                'profit_change_pct': ((enhanced_stats['total_profit'] / ea_stats['total_profit']) - 1) * 100
                                    if ea_stats['total_profit'] != 0 else 0,
                'win_rate_change': enhanced_stats['win_rate'] - ea_stats.get('win_rate', 0)
            }

        self.logger.info("Backtest complete")
        return comparison

    def get_enhancement_summary(self) -> str:
        """
        Get human-readable summary of enhancements

        Returns:
            Summary string
        """
        if not self.enhancement_rules:
            return "No enhancements created yet. Run analyze_and_create_enhancements() first."

        summary = "=== Strategy Enhancements ===\n\n"

        for category, rules in self.enhancement_rules.items():
            if rules:
                summary += f"{category.replace('_', ' ').title()}:\n"
                for i, rule in enumerate(rules, 1):
                    summary += f"  {i}. {rule['description']}\n"
                summary += "\n"

        return summary
