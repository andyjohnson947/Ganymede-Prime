"""
EA Reverse Engineering Example
Comprehensive dynamic analysis of EA behavior including:
- Entry strategy identification (VWAP bands, market structure)
- Capital recovery mechanisms (martingale, DCA, hedging)
- Risk assessment and recommendations
"""

import sys
from pathlib import Path
import time
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bot import MT5TradingBot
from src.utils import load_config, load_credentials, setup_logging
from src.ea_mining import EAMonitor, EAAnalyzer

# Import comprehensive analysis functions from reverse_engineer_ea
sys.path.insert(0, str(Path(__file__).parent.parent))
from reverse_engineer_ea import (
    analyze_trade_entry_conditions,
    find_trade_patterns,
    analyze_vwap_mean_reversion,
    analyze_hedging_and_recovery,
    analyze_position_management
)


def main():
    print("\n" + "=" * 60)
    print("  EA REVERSE ENGINEERING & ENHANCEMENT")
    print("=" * 60 + "\n")

    # Load configuration
    config = load_config()
    credentials = load_credentials()
    logger = setup_logging(config)

    # Create bot
    bot = MT5TradingBot(config, credentials)

    if not bot.start():
        print("❌ Failed to connect to MT5")
        return

    print("✅ Connected to MT5\n")

    # ===================================================================
    # STEP 1: Monitor Your Existing EA
    # ===================================================================
    print("=" * 60)
    print("STEP 1: Monitoring Your EA")
    print("=" * 60 + "\n")

    # Create EA monitor
    ea_monitor = EAMonitor(bot.mt5_manager, bot.storage)

    # Start monitoring (set magic_number if your EA uses one)
    # magic_number = 12345  # Your EA's magic number
    # ea_monitor.start_monitoring(magic_number=magic_number)

    ea_monitor.start_monitoring()  # Monitor all trades

    # Get EA statistics
    ea_stats = ea_monitor.get_ea_statistics()

    print(f"EA Statistics:")
    print(f"  Total Trades:    {ea_stats.get('total_trades', 0)}")
    print(f"  Open Trades:     {ea_stats.get('open_trades', 0)}")
    print(f"  Win Rate:        {ea_stats.get('win_rate', 0):.1f}%")
    print(f"  Total Profit:    ${ea_stats.get('total_profit', 0):.2f}")
    print(f"  Average Win:     ${ea_stats.get('average_win', 0):.2f}")
    print(f"  Average Loss:    ${ea_stats.get('average_loss', 0):.2f}")
    print(f"  Profit Factor:   {ea_stats.get('profit_factor', 0):.2f}")

    if ea_stats.get('total_trades', 0) == 0:
        print("\n⚠️  No trades found!")
        print("   Make sure your EA is running and has made some trades.")
        print("   This script monitors the EA's historical trades to learn from them.")
        bot.stop()
        return

    # ===================================================================
    # STEP 2: Analyze EA Behavior (Reverse Engineer)
    # ===================================================================
    print("\n" + "=" * 60)
    print("STEP 2: Analyzing EA Behavior")
    print("=" * 60 + "\n")

    ea_analyzer = EAAnalyzer(ea_monitor)

    # Generate full analysis report
    report = ea_analyzer.generate_full_report()

    # Entry patterns
    print("Entry Patterns:")
    entry_patterns = report['entry_patterns']
    if 'most_active_hour' in entry_patterns:
        print(f"  Most Active Hour: {entry_patterns['most_active_hour']}:00")

    if 'trade_direction_preference' in entry_patterns:
        pref = entry_patterns['trade_direction_preference']
        print(f"  Direction Preference: {pref['buy']} buys, {pref['sell']} sells ({pref['buy_percentage']:.1f}% buy)")

    # Detected rules
    print("\nDetected Strategy Rules:")
    detected_rules = report['detected_rules']
    if 'detected_rules' in detected_rules:
        for i, rule in enumerate(detected_rules['detected_rules'][:5], 1):
            confidence = detected_rules['confidence'].get(rule, 0)
            print(f"  {i}. {rule} (confidence: {confidence:.1%})")

    # Weaknesses
    print("\nIdentified Weaknesses:")
    weaknesses = report['weaknesses']
    if 'issues' in weaknesses:
        for i, issue in enumerate(weaknesses['issues'][:5], 1):
            print(f"  {i}. [{issue['severity'].upper()}] {issue['description']}")

    # Improvement opportunities
    print("\nImprovement Opportunities:")
    if 'opportunities' in weaknesses:
        for i, opp in enumerate(weaknesses['opportunities'][:5], 1):
            print(f"  {i}. {opp}")

    # ===================================================================
    # STEP 3: Comprehensive Market Structure Analysis
    # ===================================================================
    print("\n" + "=" * 60)
    print("STEP 3: Comprehensive Trade Analysis")
    print("=" * 60 + "\n")

    # Get price data with indicators
    symbols = list(set(trade.symbol for trade in ea_monitor.known_trades.values()))
    print(f"Collecting price data for {len(symbols)} symbols...")

    # Get market data for analysis
    symbol = symbols[0] if symbols else 'EURUSD'
    print(f"Fetching market data for {symbol}...")

    market_data = bot.collector.get_latest_data(symbol, 'H1', bars=5000)
    if market_data is None or market_data.empty:
        print("❌ Failed to fetch market data")
        bot.stop()
        return

    # Calculate indicators
    market_data = bot.indicator_manager.calculate_all(market_data)
    print(f"✅ Loaded {len(market_data)} bars with indicators\n")

    # Get trades as dataframe
    trades_df = ea_monitor.get_trades_dataframe()

    # Analyze each trade
    print("Analyzing trade-by-trade market conditions...")
    all_conditions = []

    for idx, trade in trades_df.iterrows():
        conditions = analyze_trade_entry_conditions(trade, market_data, market_data)
        if conditions:
            all_conditions.append(conditions)

    print(f"✅ Analyzed {len(all_conditions)} trades\n")

    # ===================================================================
    # STEP 4: Entry Strategy Patterns
    # ===================================================================
    print("\n" + "=" * 60)
    print("STEP 4: Deduced Entry Rules")
    print("=" * 60 + "\n")
    feature_engineer = FeatureEngineer(ml_config)
    ea_learner = EALearner(ea_monitor, feature_engineer)

    # Train models to learn EA behavior
    print("\nTraining ML models to learn EA behavior...")
    training_results = ea_learner.train(price_data)

    if 'entry_model' in training_results:
        print("\nEntry Model (When EA Trades):")
        print(f"  Accuracy: {training_results['entry_model']['accuracy']:.1%}")
        print(f"  Training samples: {training_results['entry_model']['train_samples']}")

        print("\n  Top factors EA uses to decide when to trade:")
        for i, (feature, importance) in enumerate(
            list(training_results['entry_model']['top_features'].items())[:5], 1
        ):
            print(f"    {i}. {feature}: {importance:.3f}")

    if 'direction_model' in training_results:
        print("\nDirection Model (Buy vs Sell):")
        print(f"  Accuracy: {training_results['direction_model']['accuracy']:.1%}")

        print("\n  Top factors EA uses to decide direction:")
        for i, (feature, importance) in enumerate(
            list(training_results['direction_model']['top_features'].items())[:5], 1
        ):
            print(f"    {i}. {feature}: {importance:.3f}")

    # ===================================================================
    # STEP 4: Create Enhanced Strategy
    # ===================================================================
    print("\n" + "=" * 60)
    print("STEP 4: Creating Enhanced Strategy")
    print("=" * 60 + "\n")

    strategy_enhancer = StrategyEnhancer(ea_monitor, ea_analyzer, ea_learner)

    # Analyze and create enhancements
    enhancements = strategy_enhancer.analyze_and_create_enhancements()

    print(strategy_enhancer.get_enhancement_summary())

    # ===================================================================
    # STEP 5: Test Enhanced Strategy
    # ===================================================================
    print("\n" + "=" * 60)
    print("STEP 5: Testing Enhanced Strategy")
    print("=" * 60 + "\n")

    # Enrich price data with features for predictions
    print("Enriching price data with features...")
    price_data_enriched = {}
    for symbol, df in price_data.items():
        enriched = feature_engineer.engineer_all_features(df.copy())
        price_data_enriched[symbol] = enriched
        print(f"  ✅ {symbol}: {len(enriched.columns)} features")

    # Get current market data for testing
    test_symbol = symbols[0] if symbols else 'EURUSD'
    test_data_raw = price_data.get(test_symbol)
    test_data = price_data_enriched.get(test_symbol)  # Use enriched data for predictions

    if test_data is not None and not test_data.empty:
        print(f"Testing enhanced strategy on current {test_symbol} data...\n")

        # Get EA's prediction
        ea_prediction = ea_learner.predict(test_data)

        print("Original EA Prediction:")
        print(f"  Should Trade: {ea_prediction.get('should_trade', False)}")
        if 'trade_probability' in ea_prediction:
            print(f"  Probability:  {ea_prediction['trade_probability']:.1%}")
        if 'direction' in ea_prediction and ea_prediction['direction'] is not None:
            print(f"  Direction:    {ea_prediction['direction'].upper()}")

        # Get enhanced signal
        enhanced_signal = strategy_enhancer.generate_enhanced_signal(test_data, ea_prediction)

        print("\nEnhanced Strategy Signal:")
        enh = enhanced_signal['enhanced_signal']
        print(f"  Should Trade: {enh['should_trade']}")
        print(f"  Confidence:   {enh['confidence']:.1%}")
        if enh['should_trade'] and enh.get('direction'):
            print(f"  Direction:    {enh['direction'].upper()}")
            print(f"  SL Adjustment: {enh['stop_loss_multiplier']:.0%}")
            print(f"  TP Adjustment: {enh['take_profit_multiplier']:.0%}")

        if enhanced_signal['modifications']:
            print("\n  Modifications Applied:")
            for mod in enhanced_signal['modifications']:
                print(f"    • {mod}")

        if enhanced_signal['filters_applied']:
            print("\n  Filters Applied:")
            for filt in enhanced_signal['filters_applied']:
                print(f"    • {filt}")

    # ===================================================================
    # STEP 6: Backtest Comparison
    # ===================================================================
    print("\n" + "=" * 60)
    print("STEP 6: Backtesting Enhanced vs Original")
    print("=" * 60 + "\n")

    comparison = strategy_enhancer.backtest_enhancements(price_data_enriched)

    print("Performance Comparison:")
    print("\nOriginal EA:")
    orig = comparison['original_ea']
    print(f"  Total Trades: {orig.get('total_trades', 0)}")
    print(f"  Win Rate:     {orig.get('win_rate', 0):.1f}%")
    print(f"  Total Profit: ${orig.get('total_profit', 0):.2f}")

    print("\nEnhanced Strategy:")
    enh = comparison['enhanced_strategy']
    if enh:
        print(f"  Total Trades: {enh.get('total_trades', 0)}")
        print(f"  Win Rate:     {enh.get('win_rate', 0):.1f}%")
        print(f"  Total Profit: ${enh.get('total_profit', 0):.2f}")

        if 'improvement' in comparison:
            imp = comparison['improvement']
            print("\nImprovement:")
            print(f"  Profit Change: ${imp.get('profit_change', 0):.2f} ({imp.get('profit_change_pct', 0):+.1f}%)")
            print(f"  Win Rate Change: {imp.get('win_rate_change', 0):+.1f}%")

        print(f"\nTrades Filtered Out: {comparison.get('trades_filtered', 0)}")

    # ===================================================================
    # STEP 7: Analyze Trade Patterns (Grid/DCA/Hedge)
    # ===================================================================
    print("\n" + "=" * 60)
    print("STEP 7: Analyzing Trade Patterns (Grid/DCA/Hedge)")
    print("=" * 60 + "\n")

    # Get all trades from EA monitor
    all_trades_df = ea_monitor.get_trades_dataframe()

    if not all_trades_df.empty:
        print(f"Analyzing {len(all_trades_df)} trades for patterns...\n")

        # Detect grid patterns (equal spacing)
        grid_patterns = []
        dca_patterns = []
        hedge_patterns = []

        for symbol in all_trades_df['symbol'].unique():
            symbol_trades = all_trades_df[all_trades_df['symbol'] == symbol].copy()
            symbol_trades = symbol_trades.sort_values('entry_time')

            # Look for consecutive same-direction trades (potential grid/DCA)
            i = 0
            while i < len(symbol_trades):
                current = symbol_trades.iloc[i]
                related_trades = [current]

                # Look ahead for similar trades within 24 hours
                j = i + 1
                while j < len(symbol_trades):
                    next_trade = symbol_trades.iloc[j]
                    time_diff_hours = (next_trade['entry_time'] - current['entry_time']).total_seconds() / 3600

                    if next_trade['type'] == current['type'] and time_diff_hours < 24:
                        related_trades.append(next_trade)
                        j += 1
                    else:
                        break

                # Analyze if we found a pattern
                if len(related_trades) >= 2:
                    prices = [t['entry_price'] for t in related_trades]
                    price_diffs = [abs(prices[k+1] - prices[k]) for k in range(len(prices)-1)]
                    avg_spacing = sum(price_diffs) / len(price_diffs) if price_diffs else 0
                    spacing_std = pd.Series(price_diffs).std() if len(price_diffs) > 1 else 0

                    # Regular spacing = grid, irregular = DCA
                    is_grid = spacing_std < avg_spacing * 0.3 if avg_spacing > 0 else False

                    pattern = {
                        'type': 'GRID' if is_grid else 'DCA',
                        'symbol': symbol,
                        'direction': current['type'],
                        'count': len(related_trades),
                        'avg_spacing': avg_spacing,
                        'first_entry': related_trades[0]['entry_time'],
                        'total_volume': sum(t['volume'] for t in related_trades),
                        'total_profit': sum(t['profit'] for t in related_trades if pd.notna(t['profit']))
                    }

                    if is_grid:
                        grid_patterns.append(pattern)
                    else:
                        dca_patterns.append(pattern)

                i = j if j > i + 1 else i + 1

            # Look for hedge patterns (opposite directions close in time)
            for i in range(len(symbol_trades)):
                for j in range(i + 1, min(i + 5, len(symbol_trades))):
                    trade1 = symbol_trades.iloc[i]
                    trade2 = symbol_trades.iloc[j]

                    time_diff_min = (trade2['entry_time'] - trade1['entry_time']).total_seconds() / 60

                    if (trade1['type'] != trade2['type'] and
                        time_diff_min < 60 and
                        abs(trade1['entry_price'] - trade2['entry_price']) < trade1['entry_price'] * 0.01):

                        hedge_patterns.append({
                            'symbol': symbol,
                            'time_diff_min': time_diff_min,
                            'price_diff': abs(trade1['entry_price'] - trade2['entry_price']),
                            'trade1_type': trade1['type'],
                            'trade2_type': trade2['type']
                        })

        # Display results
        print(f"📐 GRID PATTERNS: {len(grid_patterns)}")
        if grid_patterns:
            for idx, p in enumerate(grid_patterns[:5], 1):
                print(f"  [{idx}] {p['symbol']} {p['direction'].upper()}: {p['count']} trades, "
                      f"avg spacing: {p['avg_spacing']:.5f}, P/L: ${p['total_profit']:.2f}")

        print(f"\n💰 DCA PATTERNS: {len(dca_patterns)}")
        if dca_patterns:
            for idx, p in enumerate(dca_patterns[:5], 1):
                print(f"  [{idx}] {p['symbol']} {p['direction'].upper()}: {p['count']} trades, "
                      f"irregular spacing, P/L: ${p['total_profit']:.2f}")

        print(f"\n⚖️  HEDGE PATTERNS: {len(hedge_patterns)}")
        if hedge_patterns:
            for idx, p in enumerate(hedge_patterns[:5], 1):
                print(f"  [{idx}] {p['symbol']}: {p['trade1_type']} → {p['trade2_type']} "
                      f"within {p['time_diff_min']:.1f} min")

        # Conclusion
        print("\n📊 STRATEGY IDENTIFICATION:")
        if len(grid_patterns) > len(dca_patterns) * 2:
            print("  ✅ Primary Strategy: GRID TRADING")
            print("     EA uses regular price intervals to scale into positions")
        elif len(dca_patterns) > 0:
            print("  ✅ Primary Strategy: DOLLAR COST AVERAGING (DCA)")
            print("     EA adds to losing positions with irregular spacing")
        else:
            print("  ✅ Primary Strategy: SINGLE ENTRY")
            print("     EA does not use grid or DCA - one entry per signal")

        if len(hedge_patterns) > 5:
            print("\n  ⚖️  HEDGING DETECTED:")
            print("     EA opens opposite positions to hedge risk")

        print()
    else:
        print("No trades available for pattern analysis\n")

    # ===================================================================
    # Summary
    # ===================================================================
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60 + "\n")

    print("✅ Your EA has been reverse engineered!")
    print(f"   • Analyzed {ea_stats.get('total_trades', 0)} historical trades")
    print(f"   • Identified {len(detected_rules.get('detected_rules', []))} strategy rules")
    print(f"   • Found {len(weaknesses.get('issues', []))} weaknesses")
    print(f"   • Created {sum(len(v) for v in enhancements.values())} enhancements")
    print(f"   • ML model accuracy: {training_results.get('entry_model', {}).get('accuracy', 0):.1%}")

    print("\n💡 Next Steps:")
    print("   1. Review the enhancements above")
    print("   2. Paper trade the enhanced strategy")
    print("   3. Compare live performance")
    print("   4. Iterate and improve")

    # Stop bot
    bot.stop()
    print("\n✅ EA Analysis Complete!")


if __name__ == "__main__":
    main()
