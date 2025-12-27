#!/usr/bin/env python3
"""
Quick Backtest for December 19, 2025
Tests the doubled lookback with proper weekend bypass
"""

import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading_bot.backtesting.backtester import Backtester
from trading_bot.backtesting.performance import PerformanceAnalyzer
from trading_bot.utils.logger import logger


def main():
    """Run backtest for December 19, 2025"""

    # Backtest configuration
    symbols = ['EURUSD', 'GBPUSD']
    start_date = datetime(2025, 12, 19, 0, 0, 0)  # Dec 19, 2025
    end_date = datetime(2025, 12, 19, 23, 59, 59)  # End of Dec 19
    initial_balance = 1000.0
    spread_pips = 1.0

    logger.info("=" * 80)
    logger.info("BACKTEST: December 19, 2025")
    logger.info("=" * 80)
    logger.info(f"Symbols: {', '.join(symbols)}")
    logger.info(f"Date: {start_date.strftime('%Y-%m-%d')} (Thursday)")
    logger.info(f"Initial Balance: ${initial_balance:.2f}")
    logger.info(f"Spread: {spread_pips} pips")
    logger.info()

    # Initialize backtester
    logger.info("Initializing backtester...")
    backtester = Backtester(
        initial_balance=initial_balance,
        spread_pips=spread_pips,
        symbols=symbols
    )

    # Load data from MT5
    logger.info("Loading data from MT5...")
    try:
        backtester.load_all_data(
            data_source='mt5',
            start_date=start_date,
            end_date=end_date
        )
    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        logger.error("Make sure MT5 is connected and you have the symbols available")
        return

    # Run backtest
    logger.info("Running backtest...")
    backtester.run(check_interval_hours=1)

    # Get results
    results = backtester.get_results()

    # Print summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("BACKTEST RESULTS - December 19, 2025")
    logger.info("=" * 80)
    logger.info(f"Initial Balance: ${results['initial_balance']:.2f}")
    logger.info(f"Final Balance: ${results['final_balance']:.2f}")
    logger.info(f"Total Profit: ${results['total_profit']:.2f}")
    logger.info(f"Return: {results['return_pct']:.2f}%")
    logger.info("")
    logger.info(f"Total Trades: {results['total_trades']}")
    logger.info(f"Winning Trades: {results['winning_trades']}")
    logger.info(f"Losing Trades: {results['losing_trades']}")
    logger.info(f"Win Rate: {results['win_rate']:.1f}%")
    logger.info("")

    if results['total_trades'] > 0:
        logger.info("Trade Details:")
        logger.info("-" * 80)
        for i, trade in enumerate(results['trades'], 1):
            entry_time = trade['entry_time'].strftime('%Y-%m-%d %H:%M')
            exit_time = trade['exit_time'].strftime('%Y-%m-%d %H:%M') if trade['exit_time'] else 'Open'
            logger.info(f"#{i}: {trade['symbol']} {trade['type'].upper()} @ {entry_time}")
            logger.info(f"    Entry: {trade['entry_price']:.5f} | Exit: {trade.get('exit_price', 'N/A')}")
            logger.info(f"    Profit: ${trade.get('profit', 0):.2f}")
            logger.info("")

        # Performance analysis
        analyzer = PerformanceAnalyzer(results)
        metrics = analyzer.calculate_metrics()

        logger.info("Performance Metrics:")
        logger.info("-" * 80)
        logger.info(f"Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
        logger.info(f"Sharpe Ratio: {metrics.get('sharpe_ratio', 'N/A')}")
        logger.info(f"Profit Factor: {metrics.get('profit_factor', 'N/A')}")
        logger.info("")

    else:
        logger.warning("No trades were executed during the backtest")
        logger.warning("Check:")
        logger.warning("  - Confluence score requirements")
        logger.warning("  - Market regime (was it trending or ranging?)")
        logger.warning("  - Time filters (were MR/BO hours active?)")

    logger.info("=" * 80)


if __name__ == "__main__":
    main()
