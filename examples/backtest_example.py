#!/usr/bin/env python3
"""
Example: Running a Backtest
Demonstrates how to use the backtesting framework programmatically
"""

import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from trading_bot.backtesting import Backtester, PerformanceAnalyzer


def main():
    """Run a simple backtest example"""

    print("=" * 80)
    print("Backtesting Example")
    print("=" * 80)

    # Configuration
    symbols = ['EURUSD', 'GBPUSD']
    initial_balance = 10000.0
    spread_pips = 1.0
    days_to_test = 30

    print(f"\nConfiguration:")
    print(f"  Symbols: {', '.join(symbols)}")
    print(f"  Initial Balance: ${initial_balance:,.2f}")
    print(f"  Spread: {spread_pips} pips")
    print(f"  Period: Last {days_to_test} days")

    # Initialize backtester
    print("\n[1/4] Initializing backtester...")
    backtester = Backtester(
        initial_balance=initial_balance,
        spread_pips=spread_pips,
        symbols=symbols
    )

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_to_test)

    print(f"  Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    # Load data from MT5
    print("\n[2/4] Loading historical data from MT5...")
    try:
        # Initialize MT5
        import MetaTrader5 as mt5

        if not mt5.initialize():
            print("  ❌ Failed to initialize MT5")
            print("  Make sure MT5 is installed and configured")
            return

        print("  ✓ MT5 connected")

        # Load data
        backtester.load_all_data('mt5', start_date, end_date)

        print("  ✓ Data loaded successfully")

        # Shutdown MT5 (backtester has copied the data)
        mt5.shutdown()

    except ImportError:
        print("  ❌ MetaTrader5 package not installed")
        print("  Install with: pip install MetaTrader5")
        return

    except Exception as e:
        print(f"  ❌ Error loading data: {e}")
        return

    # Run backtest
    print("\n[3/4] Running backtest...")
    print("  This may take a few minutes...")

    try:
        backtester.run(check_interval_hours=1)
        print("  ✓ Backtest completed")

    except Exception as e:
        print(f"  ❌ Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Analyze results
    print("\n[4/4] Analyzing results...")
    results = backtester.get_results()
    analyzer = PerformanceAnalyzer(results)

    # Print summary
    backtester.print_summary()

    # Generate detailed report
    print("\nGenerating detailed report...")
    report = analyzer.generate_report('backtest_report.txt')
    print("✓ Report saved to: backtest_report.txt")

    # Export trades
    print("\nExporting trade data...")
    analyzer.export_trades_to_csv('backtest_trades.csv')
    print("✓ Trades exported to: backtest_trades.csv")

    # Export equity curve
    analyzer.export_equity_curve_to_csv('backtest_equity.csv')
    print("✓ Equity curve exported to: backtest_equity.csv")

    # Additional analysis
    print("\n" + "=" * 80)
    print("ADDITIONAL ANALYSIS")
    print("=" * 80)

    # Risk metrics
    sharpe = analyzer.calculate_sharpe_ratio()
    sortino = analyzer.calculate_sortino_ratio()
    calmar = analyzer.calculate_calmar_ratio()

    print(f"\n📊 Risk-Adjusted Returns:")
    print(f"  Sharpe Ratio:  {sharpe:>8.2f}  {'(Excellent)' if sharpe > 2 else '(Good)' if sharpe > 1.5 else '(Fair)' if sharpe > 1 else '(Poor)'}")
    print(f"  Sortino Ratio: {sortino:>8.2f}  {'(Excellent)' if sortino > 2.5 else '(Good)' if sortino > 2 else '(Fair)' if sortino > 1.5 else '(Poor)'}")
    print(f"  Calmar Ratio:  {calmar:>8.2f}  {'(Excellent)' if calmar > 3 else '(Good)' if calmar > 2 else '(Fair)' if calmar > 1 else '(Poor)'}")

    # Strategy breakdown
    strategy_stats = analyzer.analyze_by_strategy()

    print(f"\n🎯 Performance by Strategy:")
    for strategy, stats in strategy_stats.items():
        print(f"\n  {strategy}:")
        print(f"    Trades:        {stats['total_trades']}")
        print(f"    Win Rate:      {stats['win_rate']:.1f}%")
        print(f"    Total Profit:  ${stats['total_profit']:,.2f}")
        print(f"    Avg Profit:    ${stats['avg_profit']:,.2f}")
        print(f"    Avg Duration:  {stats['avg_duration_hours']:.1f} hours")

    # Consecutive trades
    consec = analyzer.analyze_consecutive_trades()

    print(f"\n🔄 Consecutive Trades:")
    print(f"  Max Consecutive Wins:   {consec['max_consecutive_wins']}")
    print(f"  Max Consecutive Losses: {consec['max_consecutive_losses']}")
    print(f"  Avg Consecutive Wins:   {consec['avg_consecutive_wins']:.1f}")
    print(f"  Avg Consecutive Losses: {consec['avg_consecutive_losses']:.1f}")

    # Trading patterns
    print(f"\n📅 Best Day of Week:")
    daily_stats = analyzer.analyze_by_day_of_week()
    if daily_stats:
        best_day = max(daily_stats.items(), key=lambda x: x[1]['total_profit'])
        print(f"  {best_day[0]}: ${best_day[1]['total_profit']:,.2f} ({best_day[1]['total_trades']} trades, {best_day[1]['win_rate']:.1f}% win rate)")

    print(f"\n🕐 Best Hour of Day:")
    hourly_stats = analyzer.analyze_by_hour()
    if hourly_stats:
        best_hour = max(hourly_stats.items(), key=lambda x: x[1]['total_profit'])
        print(f"  Hour {best_hour[0]:02d}:00: ${best_hour[1]['total_profit']:,.2f} ({best_hour[1]['total_trades']} trades, {best_hour[1]['win_rate']:.1f}% win rate)")

    # Drawdown analysis
    dd_analysis = analyzer.analyze_drawdowns()

    print(f"\n📉 Drawdown Analysis:")
    print(f"  Max Drawdown:       ${dd_analysis['max_drawdown']:,.2f} ({dd_analysis['max_drawdown_pct']:.2f}%)")
    print(f"  Avg Drawdown:       ${dd_analysis['avg_drawdown']:,.2f}")
    print(f"  Max DD Duration:    {dd_analysis['max_drawdown_duration_days']:.1f} days")
    print(f"  Drawdown Periods:   {len(dd_analysis['drawdown_periods'])}")

    print("\n" + "=" * 80)
    print("✅ Backtesting complete!")
    print("=" * 80)
    print("\nGenerated files:")
    print("  - backtest_report.txt    (Detailed performance report)")
    print("  - backtest_trades.csv    (All trades)")
    print("  - backtest_equity.csv    (Equity curve)")


if __name__ == '__main__':
    main()
