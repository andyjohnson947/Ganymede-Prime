"""
Regime Detection Optimizer - Find Sweet Spot for Hurst + VHF + ADX

Tests different threshold combinations to find optimal regime detection:
- Hurst alone vs Hurst+VHF vs Hurst+VHF+ADX
- Different threshold values
- Measures accuracy against actual trade outcomes

Usage:
    from diagnostics.regime_optimizer import RegimeOptimizer

    optimizer = RegimeOptimizer(mt5_manager, data_store)
    results = optimizer.optimize_thresholds(symbols=['GBPUSD'], days=30)
    optimizer.print_results(results)
"""

from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from collections import defaultdict
import statistics


class RegimeOptimizer:
    """Optimize regime detection thresholds"""

    def __init__(self, mt5_manager, data_store):
        """
        Initialize optimizer

        Args:
            mt5_manager: MT5Manager instance for price data
            data_store: DataStore instance for trade history
        """
        self.mt5 = mt5_manager
        self.data_store = data_store

    def optimize_thresholds(
        self,
        symbols: List[str],
        days: int = 30,
        min_trades_per_regime: int = 10
    ) -> Dict:
        """
        Test different threshold combinations to find optimal regime detection

        Args:
            symbols: Symbols to analyze
            days: Days of history to analyze
            min_trades_per_regime: Minimum trades needed for statistical significance

        Returns:
            Dict with optimization results
        """
        print(f"\n{'='*80}")
        print(f"🎯 REGIME DETECTION OPTIMIZER")
        print(f"{'='*80}")
        print(f"Finding sweet spot for Hurst + VHF + ADX thresholds...")
        print(f"Analyzing {len(symbols)} symbol(s) over {days} days\n")

        results = {
            'symbols': symbols,
            'days': days,
            'analysis_date': datetime.now().isoformat(),
        }

        # Get historical data
        print("📥 Loading historical data...")
        trades = self.data_store.get_trades(days=days)
        print(f"   ✅ Loaded {len(trades)} trades\n")

        if len(trades) < min_trades_per_regime:
            results['error'] = f"Need at least {min_trades_per_regime} trades (found {len(trades)})"
            return results

        # Calculate regime indicators for each trade
        print("📊 Calculating regime indicators for each trade...")
        trade_regimes = self._calculate_trade_regimes(trades, symbols)
        print(f"   ✅ Calculated regimes for {len(trade_regimes)} trades\n")

        # Test different threshold combinations
        print("🔬 Testing threshold combinations...\n")

        # 1. Test Hurst alone
        print("1️⃣  Testing HURST alone...")
        results['hurst_alone'] = self._test_hurst_thresholds(trade_regimes)

        # 2. Test VHF alone
        print("2️⃣  Testing VHF alone...")
        results['vhf_alone'] = self._test_vhf_thresholds(trade_regimes)

        # 3. Test ADX alone (baseline)
        print("3️⃣  Testing ADX alone (baseline)...")
        results['adx_alone'] = self._test_adx_thresholds(trade_regimes)

        # 4. Test Hurst + VHF (current implementation)
        print("4️⃣  Testing HURST + VHF (current)...")
        results['hurst_vhf'] = self._test_hurst_vhf_combinations(trade_regimes)

        # 5. Test Hurst + VHF + ADX
        print("5️⃣  Testing HURST + VHF + ADX (confluence)...")
        results['hurst_vhf_adx'] = self._test_triple_combinations(trade_regimes)

        # Find best overall combination
        print("\n🏆 Finding optimal configuration...")
        results['best_config'] = self._find_best_configuration(results)

        return results

    def _calculate_trade_regimes(
        self,
        trades: List[Dict],
        symbols: List[str]
    ) -> List[Dict]:
        """Calculate regime indicators at trade entry time"""
        from indicators.advanced_regime_detector import AdvancedRegimeDetector
        from indicators.market_analyzer import MarketAnalyzer

        regime_detector = AdvancedRegimeDetector()
        market_analyzer = MarketAnalyzer()

        trade_regimes = []

        for trade in trades:
            symbol = trade.get('symbol')
            if symbol not in symbols:
                continue

            # Get price data around trade entry time
            # Use 150 bars to ensure enough for Hurst calculation
            try:
                price_data = self.mt5.get_historical_data(symbol, 'H1', bars=150)

                if price_data is None or len(price_data) < 100:
                    continue

                # Calculate regime indicators
                hurst = regime_detector.calculate_hurst_exponent(price_data)
                vhf = regime_detector.calculate_vhf(price_data)

                # Calculate ADX
                market_condition = market_analyzer.analyze_market_condition(price_data)
                adx = market_condition.get('adx')

                if hurst is not None and vhf is not None and adx is not None:
                    trade_regimes.append({
                        'ticket': trade.get('ticket'),
                        'symbol': symbol,
                        'profit': trade.get('profit', 0),
                        'win': trade.get('profit', 0) > 0,
                        'hurst': hurst,
                        'vhf': vhf,
                        'adx': adx,
                    })

            except Exception as e:
                # Skip trades we can't get data for
                continue

        return trade_regimes

    def _test_hurst_thresholds(self, trade_regimes: List[Dict]) -> Dict:
        """Test different Hurst thresholds"""
        # Test ranging thresholds: 0.40, 0.42, 0.45, 0.47, 0.50
        # Test trending thresholds: 0.50, 0.52, 0.55, 0.57, 0.60

        ranging_thresholds = [0.40, 0.42, 0.45, 0.47, 0.50]
        trending_thresholds = [0.50, 0.52, 0.55, 0.57, 0.60]

        results = {}

        for ranging_thresh in ranging_thresholds:
            for trending_thresh in trending_thresholds:
                if ranging_thresh >= trending_thresh:
                    continue

                key = f"H<{ranging_thresh}_H>{trending_thresh}"

                # Classify trades
                ranging_trades = [t for t in trade_regimes if t['hurst'] < ranging_thresh]
                trending_trades = [t for t in trade_regimes if t['hurst'] > trending_thresh]
                transitional_trades = [
                    t for t in trade_regimes
                    if ranging_thresh <= t['hurst'] <= trending_thresh
                ]

                # Calculate metrics
                ranging_wr = self._calculate_win_rate(ranging_trades)
                trending_wr = self._calculate_win_rate(trending_trades)
                transitional_wr = self._calculate_win_rate(transitional_trades)

                # Score: higher ranging WR is good, lower trending WR is good
                score = 0
                if len(ranging_trades) >= 5:
                    score += ranging_wr
                if len(trending_trades) >= 5:
                    score += (100 - trending_wr)  # Invert: want LOW win rate in trending

                # Normalize by coverage
                total_classified = len(ranging_trades) + len(trending_trades)
                coverage = total_classified / len(trade_regimes) * 100 if trade_regimes else 0

                results[key] = {
                    'ranging_threshold': ranging_thresh,
                    'trending_threshold': trending_thresh,
                    'ranging_trades': len(ranging_trades),
                    'trending_trades': len(trending_trades),
                    'transitional_trades': len(transitional_trades),
                    'ranging_wr': ranging_wr,
                    'trending_wr': trending_wr,
                    'transitional_wr': transitional_wr,
                    'score': score,
                    'coverage': coverage,
                }

        # Sort by score
        results = dict(sorted(results.items(), key=lambda x: x[1]['score'], reverse=True))

        return results

    def _test_vhf_thresholds(self, trade_regimes: List[Dict]) -> Dict:
        """Test different VHF thresholds"""
        # Test ranging thresholds: 0.20, 0.23, 0.25, 0.27, 0.30
        # Test trending thresholds: 0.35, 0.38, 0.40, 0.42, 0.45

        ranging_thresholds = [0.20, 0.23, 0.25, 0.27, 0.30]
        trending_thresholds = [0.35, 0.38, 0.40, 0.42, 0.45]

        results = {}

        for ranging_thresh in ranging_thresholds:
            for trending_thresh in trending_thresholds:
                if ranging_thresh >= trending_thresh:
                    continue

                key = f"VHF<{ranging_thresh}_VHF>{trending_thresh}"

                ranging_trades = [t for t in trade_regimes if t['vhf'] < ranging_thresh]
                trending_trades = [t for t in trade_regimes if t['vhf'] > trending_thresh]
                transitional_trades = [
                    t for t in trade_regimes
                    if ranging_thresh <= t['vhf'] <= trending_thresh
                ]

                ranging_wr = self._calculate_win_rate(ranging_trades)
                trending_wr = self._calculate_win_rate(trending_trades)

                score = 0
                if len(ranging_trades) >= 5:
                    score += ranging_wr
                if len(trending_trades) >= 5:
                    score += (100 - trending_wr)

                total_classified = len(ranging_trades) + len(trending_trades)
                coverage = total_classified / len(trade_regimes) * 100 if trade_regimes else 0

                results[key] = {
                    'ranging_threshold': ranging_thresh,
                    'trending_threshold': trending_thresh,
                    'ranging_trades': len(ranging_trades),
                    'trending_trades': len(trending_trades),
                    'transitional_trades': len(transitional_trades),
                    'ranging_wr': ranging_wr,
                    'trending_wr': trending_wr,
                    'score': score,
                    'coverage': coverage,
                }

        results = dict(sorted(results.items(), key=lambda x: x[1]['score'], reverse=True))

        return results

    def _test_adx_thresholds(self, trade_regimes: List[Dict]) -> Dict:
        """Test different ADX thresholds (baseline comparison)"""
        # Test ranging: ADX < threshold
        # Test trending: ADX > threshold

        thresholds = [15, 18, 20, 22, 25, 28, 30]

        results = {}

        for thresh in thresholds:
            key = f"ADX<{thresh}_ADX>{thresh+5}"

            ranging_trades = [t for t in trade_regimes if t['adx'] < thresh]
            trending_trades = [t for t in trade_regimes if t['adx'] > thresh + 5]

            ranging_wr = self._calculate_win_rate(ranging_trades)
            trending_wr = self._calculate_win_rate(trending_trades)

            score = 0
            if len(ranging_trades) >= 5:
                score += ranging_wr
            if len(trending_trades) >= 5:
                score += (100 - trending_wr)

            total_classified = len(ranging_trades) + len(trending_trades)
            coverage = total_classified / len(trade_regimes) * 100 if trade_regimes else 0

            results[key] = {
                'ranging_threshold': thresh,
                'trending_threshold': thresh + 5,
                'ranging_trades': len(ranging_trades),
                'trending_trades': len(trending_trades),
                'ranging_wr': ranging_wr,
                'trending_wr': trending_wr,
                'score': score,
                'coverage': coverage,
            }

        results = dict(sorted(results.items(), key=lambda x: x[1]['score'], reverse=True))

        return results

    def _test_hurst_vhf_combinations(self, trade_regimes: List[Dict]) -> Dict:
        """Test Hurst + VHF combinations (current implementation)"""
        # Test key combinations
        hurst_ranging = [0.45, 0.47, 0.50]
        hurst_trending = [0.52, 0.55, 0.57]
        vhf_ranging = [0.25, 0.27, 0.30]
        vhf_trending = [0.38, 0.40, 0.42]

        results = {}

        for h_range in hurst_ranging:
            for h_trend in hurst_trending:
                if h_range >= h_trend:
                    continue

                for v_range in vhf_ranging:
                    for v_trend in vhf_trending:
                        if v_range >= v_trend:
                            continue

                        key = f"H<{h_range}+VHF<{v_range}_H>{h_trend}+VHF>{v_trend}"

                        # Classify: BOTH must agree
                        ranging_trades = [
                            t for t in trade_regimes
                            if t['hurst'] < h_range and t['vhf'] < v_range
                        ]
                        trending_trades = [
                            t for t in trade_regimes
                            if t['hurst'] > h_trend or t['vhf'] > v_trend  # OR logic like current impl
                        ]

                        ranging_wr = self._calculate_win_rate(ranging_trades)
                        trending_wr = self._calculate_win_rate(trending_trades)

                        score = 0
                        if len(ranging_trades) >= 5:
                            score += ranging_wr
                        if len(trending_trades) >= 5:
                            score += (100 - trending_wr)

                        total_classified = len(ranging_trades) + len(trending_trades)
                        coverage = total_classified / len(trade_regimes) * 100 if trade_regimes else 0

                        results[key] = {
                            'hurst_ranging': h_range,
                            'hurst_trending': h_trend,
                            'vhf_ranging': v_range,
                            'vhf_trending': v_trend,
                            'ranging_trades': len(ranging_trades),
                            'trending_trades': len(trending_trades),
                            'ranging_wr': ranging_wr,
                            'trending_wr': trending_wr,
                            'score': score,
                            'coverage': coverage,
                        }

        results = dict(sorted(results.items(), key=lambda x: x[1]['score'], reverse=True))

        return results

    def _test_triple_combinations(self, trade_regimes: List[Dict]) -> Dict:
        """Test Hurst + VHF + ADX combinations"""
        # Test with ADX as confirmation
        # Ranging: Hurst < X AND VHF < Y AND ADX < Z
        # Trending: Hurst > X OR VHF > Y OR ADX > Z

        configs = [
            # (h_range, h_trend, v_range, v_trend, adx_range, adx_trend)
            (0.45, 0.55, 0.25, 0.40, 20, 25),
            (0.45, 0.55, 0.27, 0.40, 20, 25),
            (0.47, 0.55, 0.25, 0.40, 20, 25),
            (0.45, 0.57, 0.25, 0.40, 20, 25),
            (0.45, 0.55, 0.25, 0.42, 20, 25),
            (0.45, 0.55, 0.25, 0.40, 18, 23),
            (0.45, 0.55, 0.25, 0.40, 22, 27),
        ]

        results = {}

        for h_range, h_trend, v_range, v_trend, adx_range, adx_trend in configs:
            key = f"H<{h_range}+VHF<{v_range}+ADX<{adx_range}"

            # Triple confirmation for ranging
            ranging_trades = [
                t for t in trade_regimes
                if t['hurst'] < h_range and t['vhf'] < v_range and t['adx'] < adx_range
            ]

            # Any one indicator trending = trending
            trending_trades = [
                t for t in trade_regimes
                if t['hurst'] > h_trend or t['vhf'] > v_trend or t['adx'] > adx_trend
            ]

            ranging_wr = self._calculate_win_rate(ranging_trades)
            trending_wr = self._calculate_win_rate(trending_trades)

            score = 0
            if len(ranging_trades) >= 5:
                score += ranging_wr
            if len(trending_trades) >= 5:
                score += (100 - trending_wr)

            total_classified = len(ranging_trades) + len(trending_trades)
            coverage = total_classified / len(trade_regimes) * 100 if trade_regimes else 0

            results[key] = {
                'hurst_ranging': h_range,
                'hurst_trending': h_trend,
                'vhf_ranging': v_range,
                'vhf_trending': v_trend,
                'adx_ranging': adx_range,
                'adx_trending': adx_trend,
                'ranging_trades': len(ranging_trades),
                'trending_trades': len(trending_trades),
                'ranging_wr': ranging_wr,
                'trending_wr': trending_wr,
                'score': score,
                'coverage': coverage,
            }

        results = dict(sorted(results.items(), key=lambda x: x[1]['score'], reverse=True))

        return results

    def _calculate_win_rate(self, trades: List[Dict]) -> float:
        """Calculate win rate for a list of trades"""
        if not trades:
            return 0.0

        wins = sum(1 for t in trades if t['win'])
        return (wins / len(trades)) * 100

    def _find_best_configuration(self, results: Dict) -> Dict:
        """Find best overall configuration"""
        best = {
            'method': None,
            'config': None,
            'score': 0,
        }

        # Check each method
        for method in ['hurst_alone', 'vhf_alone', 'adx_alone', 'hurst_vhf', 'hurst_vhf_adx']:
            method_results = results.get(method, {})
            if not method_results:
                continue

            # Get top configuration for this method
            top_config = next(iter(method_results.items()), None)
            if not top_config:
                continue

            config_name, config_data = top_config
            score = config_data.get('score', 0)

            if score > best['score']:
                best['method'] = method
                best['config'] = config_name
                best['score'] = score
                best['data'] = config_data

        return best

    def print_results(self, results: Dict):
        """Print optimization results"""
        print(f"\n{'='*80}")
        print(f"🎯 REGIME OPTIMIZATION RESULTS")
        print(f"{'='*80}\n")

        if 'error' in results:
            print(f"❌ {results['error']}\n")
            return

        # Print top 3 for each method
        methods = [
            ('hurst_alone', 'HURST Alone'),
            ('vhf_alone', 'VHF Alone'),
            ('adx_alone', 'ADX Alone (Baseline)'),
            ('hurst_vhf', 'HURST + VHF (Current)'),
            ('hurst_vhf_adx', 'HURST + VHF + ADX'),
        ]

        for method_key, method_name in methods:
            method_results = results.get(method_key, {})
            if not method_results:
                continue

            print(f"{'─'*80}")
            print(f"📊 {method_name}")
            print(f"{'─'*80}\n")

            for i, (config_name, data) in enumerate(list(method_results.items())[:3], 1):
                print(f"   #{i}: {config_name}")
                print(f"      Score: {data['score']:.1f}")
                print(f"      Ranging: {data['ranging_trades']} trades, {data['ranging_wr']:.1f}% WR")
                print(f"      Trending: {data['trending_trades']} trades, {data['trending_wr']:.1f}% WR")
                print(f"      Coverage: {data.get('coverage', 0):.1f}%")
                print()

        # Print best overall
        print(f"{'='*80}")
        print(f"🏆 BEST CONFIGURATION")
        print(f"{'='*80}\n")

        best = results.get('best_config', {})
        if best.get('method'):
            print(f"   Method: {best['method'].upper().replace('_', ' + ')}")
            print(f"   Config: {best['config']}")
            print(f"   Score: {best['score']:.1f}")
            print(f"\n   Details:")
            data = best.get('data', {})
            print(f"      Ranging trades: {data.get('ranging_trades', 0)} ({data.get('ranging_wr', 0):.1f}% WR)")
            print(f"      Trending trades: {data.get('trending_trades', 0)} ({data.get('trending_wr', 0):.1f}% WR)")

            # Show thresholds
            print(f"\n   📝 Recommended Thresholds:")
            if 'hurst_ranging' in data:
                print(f"      HURST_RANGING_THRESHOLD = {data['hurst_ranging']}")
            if 'hurst_trending' in data:
                print(f"      HURST_TRENDING_THRESHOLD = {data['hurst_trending']}")
            if 'vhf_ranging' in data:
                print(f"      VHF_RANGING_THRESHOLD = {data['vhf_ranging']}")
            if 'vhf_trending' in data:
                print(f"      VHF_TRENDING_THRESHOLD = {data['vhf_trending']}")
            if 'adx_ranging' in data:
                print(f"      ADX_RANGING_THRESHOLD = {data['adx_ranging']}")
            if 'adx_trending' in data:
                print(f"      ADX_TRENDING_THRESHOLD = {data['adx_trending']}")

        print(f"\n{'='*80}\n")
