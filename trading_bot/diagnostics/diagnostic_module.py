"""
Diagnostic Module - Main orchestrator for trading intelligence

Runs hourly analysis and provides:
- Market condition tracking
- Performance correlation
- Recovery effectiveness
- Adaptive recommendations
"""

import threading
import time
from datetime import datetime
from typing import Dict, List, Optional
import json
from pathlib import Path

from .data_store import DataStore
from .market_analyzer import MarketAnalyzer
from .performance_analyzer import PerformanceAnalyzer
from .recovery_analyzer import RecoveryAnalyzer


class DiagnosticModule:
    """Main diagnostic module orchestrator - runs in background"""

    def __init__(self, mt5_manager, recovery_manager, data_dir: str = "data/diagnostics"):
        """
        Initialize diagnostic module

        Args:
            mt5_manager: MT5Manager instance for market data
            recovery_manager: RecoveryManager instance for recovery tracking
            data_dir: Directory for storing diagnostic data
        """
        self.mt5 = mt5_manager
        self.recovery_manager = recovery_manager

        # Components
        self.data_store = DataStore(data_dir)
        self.market_analyzer = MarketAnalyzer()
        self.performance_analyzer = PerformanceAnalyzer()
        self.recovery_analyzer = RecoveryAnalyzer()

        # Threading
        self.running = False
        self.diagnostic_thread: Optional[threading.Thread] = None

        # Timing
        self.analysis_interval = 3600  # 1 hour in seconds
        self.last_analysis = None

        # Load baseline statistics if available
        self.baseline_stats = self._load_baseline_stats()

    def _load_baseline_stats(self) -> Optional[Dict]:
        """Load baseline statistics from bootstrap"""
        stats_file = Path("recovery_stack_statistics.json")
        if stats_file.exists():
            try:
                with open(stats_file, 'r') as f:
                    return json.load(f)
            except:
                return None
        return None

    def start(self):
        """Start diagnostic module in background"""
        if self.running:
            print("⚠️  Diagnostic module already running")
            return

        self.running = True
        self.diagnostic_thread = threading.Thread(
            target=self._diagnostic_loop,
            daemon=True,
            name="DiagnosticModule"
        )
        self.diagnostic_thread.start()

        print("✅ Diagnostic module started - hourly analysis enabled")

    def stop(self):
        """Stop diagnostic module"""
        self.running = False
        if self.diagnostic_thread:
            self.diagnostic_thread.join(timeout=5)
        print("⏹ Diagnostic module stopped")

    def _diagnostic_loop(self):
        """Main diagnostic loop - runs every hour"""
        while self.running:
            try:
                # Run analysis
                self._run_hourly_analysis()

                # Wait for next interval
                time.sleep(self.analysis_interval)

            except Exception as e:
                print(f"❌ Diagnostic error: {e}")
                time.sleep(60)  # Wait 1 minute before retry

    def _run_hourly_analysis(self):
        """Run comprehensive hourly analysis"""
        print(f"\n{'='*80}")
        print(f"📊 DIAGNOSTIC ANALYSIS - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*80}\n")

        snapshot = {
            'timestamp': datetime.now().isoformat(),
        }

        # 1. Analyze market conditions
        print("🌍 Analyzing market conditions...")
        market_analysis = self._analyze_current_market()
        snapshot['market_conditions'] = market_analysis

        # 2. Analyze performance
        print("🤖 Analyzing robot performance...")
        performance_analysis = self._analyze_performance()
        snapshot['performance'] = performance_analysis

        # 3. Analyze recovery effectiveness
        print("🔧 Analyzing recovery mechanisms...")
        recovery_analysis = self._analyze_recovery()
        snapshot['recovery'] = recovery_analysis

        # 4. Generate insights and recommendations
        print("💡 Generating recommendations...")
        recommendations = self._generate_recommendations(
            market_analysis,
            performance_analysis,
            recovery_analysis
        )
        snapshot['recommendations'] = recommendations

        # Save snapshot
        self.data_store.record_hourly_snapshot(snapshot)

        # Print summary
        self._print_summary(snapshot)

        self.last_analysis = datetime.now()

    def _analyze_current_market(self) -> Dict:
        """Analyze current market conditions for all symbols"""
        market_analysis = {}

        # Get tracked symbols from recovery manager
        symbols = set()
        for pos in self.recovery_manager.tracked_positions.values():
            symbols.add(pos['symbol'])

        for symbol in symbols:
            try:
                # Get historical data
                price_data = self.mt5.get_historical_data(symbol, 'H1', bars=100)

                if price_data is not None:
                    condition = self.market_analyzer.analyze_market_condition(price_data)
                    market_analysis[symbol] = condition

                    # Record to data store
                    self.data_store.record_market_condition(symbol, condition)

            except Exception as e:
                print(f"   ⚠️  Error analyzing {symbol}: {e}")

        return market_analysis

    def _analyze_performance(self) -> Dict:
        """Analyze robot trading performance"""
        # Get recent trades
        trades = self.data_store.get_trades(days=7)

        # Analyze performance
        performance = self.performance_analyzer.analyze_performance(trades, hours=24)

        # Identify patterns
        market_conditions = self.data_store.get_market_conditions(hours=168)  # 7 days
        patterns = self.performance_analyzer.identify_patterns(trades, market_conditions)

        performance['patterns'] = patterns

        return performance

    def _analyze_recovery(self) -> Dict:
        """Analyze recovery mechanism effectiveness"""
        # Get recent recovery actions
        recovery_actions = self.data_store.get_recovery_actions(days=7)

        # Analyze effectiveness
        effectiveness = self.recovery_analyzer.analyze_recovery_effectiveness(recovery_actions)

        # Compare with baseline
        if self.baseline_stats:
            comparison = self.recovery_analyzer.compare_with_baseline(
                effectiveness,
                self.baseline_stats
            )
            effectiveness['baseline_comparison'] = comparison

        # Identify patterns
        patterns = self.recovery_analyzer.identify_recovery_patterns(recovery_actions)
        effectiveness['patterns'] = patterns

        return effectiveness

    def _generate_recommendations(
        self,
        market_analysis: Dict,
        performance_analysis: Dict,
        recovery_analysis: Dict
    ) -> List[Dict]:
        """Generate actionable recommendations"""
        recommendations = []

        # 1. Performance-based recommendations
        performance_patterns = performance_analysis.get('patterns', [])
        for pattern in performance_patterns:
            if pattern.get('severity') == 'critical':
                recommendations.append({
                    'priority': 'high',
                    'category': 'performance',
                    'message': pattern['message'],
                    'action': f"Review trading logic for {pattern.get('regime', 'unknown')} conditions",
                })

        # 2. Recovery-based recommendations
        recovery_patterns = recovery_analysis.get('patterns', [])
        for pattern in recovery_patterns:
            if pattern.get('type') == 'low_effectiveness':
                recommendations.append({
                    'priority': 'medium',
                    'category': 'recovery',
                    'message': pattern['message'],
                    'action': f"Consider adjusting {pattern['recovery_type'].upper()} parameters",
                })

        # 3. Market-based recommendations
        for symbol, condition in market_analysis.items():
            regime = condition.get('regime', 'unknown')
            adx = condition.get('adx', 0)

            # High volatility + strong trend = risky
            if adx > 30 and condition.get('volatility_percentile', 0) > 70:
                recommendations.append({
                    'priority': 'medium',
                    'category': 'market',
                    'message': f"{symbol}: High volatility + strong trend detected",
                    'action': f"Consider reducing position sizes or avoiding new entries",
                })

        # 4. Baseline comparison recommendations
        baseline_comp = recovery_analysis.get('baseline_comparison', {})
        drawdown_comp = baseline_comp.get('drawdown_vs_baseline', {})

        if drawdown_comp.get('trend') == 'worsening':
            change = drawdown_comp.get('change_percent', 0)
            if change > 20:
                recommendations.append({
                    'priority': 'high',
                    'category': 'risk',
                    'message': f"Drawdowns increased {change:.1f}% vs baseline",
                    'action': "Review recent trades and consider tightening risk parameters",
                })

        return recommendations

    def _print_summary(self, snapshot: Dict):
        """Print diagnostic summary"""
        print(f"\n📈 SUMMARY")
        print(f"{'─'*80}")

        # Performance
        perf = snapshot['performance']
        print(f"\n🤖 Performance (Last 24h):")
        print(f"   Total trades: {perf['total_trades']}")
        print(f"   Win rate: {perf['win_rate']:.1f}%")
        print(f"   Profit factor: {perf['profit_factor']:.2f}")
        print(f"   Total P&L: ${perf['total_profit']:.2f}")

        # Recovery
        recovery = snapshot['recovery']
        print(f"\n🔧 Recovery Effectiveness:")
        for rec_type in ['grid', 'hedge', 'dca']:
            metrics = recovery.get(rec_type, {})
            if metrics.get('total_triggered', 0) > 0:
                print(f"   {rec_type.upper()}: {metrics['success_rate']:.1f}% success ({metrics['total_triggered']} triggers)")

        # Stack metrics
        stack = recovery.get('stack_metrics', {})
        print(f"\n📦 Stack Metrics:")
        print(f"   Active stacks: {stack.get('total_stacks', 0)}")
        print(f"   Avg drawdown: ${stack.get('avg_max_drawdown', 0):.2f}")
        print(f"   Avg volume: {stack.get('avg_max_volume', 0):.2f} lots")

        # Recommendations
        recs = snapshot['recommendations']
        if recs:
            print(f"\n💡 Recommendations ({len(recs)}):")
            for i, rec in enumerate(recs[:3], 1):  # Show top 3
                priority_icon = '🔴' if rec['priority'] == 'high' else '🟡'
                print(f"   {priority_icon} {rec['message']}")

        print(f"\n{'='*80}\n")

    def record_trade_close(self, trade_data: Dict):
        """
        Record trade closure with market context

        Args:
            trade_data: Dict with trade details (ticket, symbol, profit, etc.)
        """
        # Get current market condition
        symbol = trade_data.get('symbol')
        if symbol:
            try:
                price_data = self.mt5.get_historical_data(symbol, 'H1', bars=50)
                if price_data is not None:
                    condition = self.market_analyzer.analyze_market_condition(price_data)
                    trade_data['market_regime'] = condition.get('regime')
                    trade_data['market_adx'] = condition.get('adx')
                    trade_data['market_volatility'] = condition.get('volatility_percentile')
            except:
                pass

        # Record to data store
        self.data_store.record_trade(trade_data)

    def record_recovery_action(self, recovery_data: Dict):
        """
        Record recovery mechanism activation

        Args:
            recovery_data: Dict with recovery details
        """
        self.data_store.record_recovery_action(recovery_data)

    def get_current_status(self) -> Dict:
        """Get current diagnostic status"""
        return {
            'running': self.running,
            'last_analysis': self.last_analysis.isoformat() if self.last_analysis else None,
            'data_stats': self.data_store.get_statistics(),
            'baseline_loaded': self.baseline_stats is not None,
        }
