#!/usr/bin/env python3
"""
Backtesting CLI
Run backtests on historical data using production strategy code
"""

import argparse
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading_bot.backtesting.backtester import Backtester
from trading_bot.backtesting.performance import PerformanceAnalyzer
from trading_bot.utils.logger import setup_logger

logger = setup_logger(__name__)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Backtest trading strategy on historical data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backtest EURUSD for last 30 days from MT5
  python backtest.py --symbols EURUSD --days 30 --source mt5

  # Backtest multiple symbols with custom dates
  python backtest.py --symbols EURUSD GBPUSD --start 2024-01-01 --end 2024-12-31 --source mt5

  # Backtest from CSV files
  python backtest.py --symbols EURUSD --days 30 --source csv --data-dir ./data

  # Custom initial balance and spread
  python backtest.py --symbols EURUSD --days 30 --balance 50000 --spread 1.5

  # Export results
  python backtest.py --symbols EURUSD --days 30 --report results.txt --trades trades.csv
        """
    )

    # Data source
    parser.add_argument(
        '--source',
        choices=['mt5', 'csv'],
        default='mt5',
        help='Data source (default: mt5)'
    )

    parser.add_argument(
        '--data-dir',
        type=str,
        help='Directory containing CSV files (required if source=csv)'
    )

    # Symbols
    parser.add_argument(
        '--symbols',
        nargs='+',
        default=['EURUSD', 'GBPUSD'],
        help='Trading symbols (default: EURUSD GBPUSD)'
    )

    # Date range
    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument(
        '--days',
        type=int,
        help='Number of days to backtest (from today backwards)'
    )
    date_group.add_argument(
        '--start',
        type=str,
        help='Start date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--end',
        type=str,
        help='End date (YYYY-MM-DD, default: today)'
    )

    # Trading parameters
    parser.add_argument(
        '--balance',
        type=float,
        default=10000.0,
        help='Initial balance (default: 10000)'
    )

    parser.add_argument(
        '--spread',
        type=float,
        default=1.0,
        help='Spread in pips (default: 1.0)'
    )

    parser.add_argument(
        '--interval',
        type=int,
        default=1,
        help='Check interval in hours (default: 1)'
    )

    # Output
    parser.add_argument(
        '--report',
        type=str,
        help='Save performance report to file'
    )

    parser.add_argument(
        '--trades',
        type=str,
        help='Export trades to CSV file'
    )

    parser.add_argument(
        '--equity',
        type=str,
        help='Export equity curve to CSV file'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress detailed logging'
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()

    # Parse dates
    if args.days:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days)
    else:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
        if args.end:
            end_date = datetime.strptime(args.end, '%Y-%m-%d')
        else:
            end_date = datetime.now()

    # Validate CSV source
    if args.source == 'csv' and not args.data_dir:
        print("Error: --data-dir required when using CSV source")
        sys.exit(1)

    # Initialize backtester
    logger.info("Initializing backtester...")
    backtester = Backtester(
        initial_balance=args.balance,
        spread_pips=args.spread,
        symbols=args.symbols
    )

    # Load data
    try:
        if args.source == 'mt5':
            logger.info("Loading data from MT5...")
            # Connect to MT5
            import MetaTrader5 as mt5
            if not mt5.initialize():
                print("Error: Failed to initialize MT5")
                sys.exit(1)

            backtester.load_all_data('mt5', start_date, end_date)

            mt5.shutdown()

        else:  # CSV
            logger.info(f"Loading data from CSV files in {args.data_dir}...")

            # Build data paths dict
            data_paths = {}
            for symbol in args.symbols:
                for timeframe in ['H1', 'D1', 'W1']:
                    filename = f"{symbol}_{timeframe}.csv"
                    filepath = os.path.join(args.data_dir, filename)

                    if not os.path.exists(filepath):
                        print(f"Warning: Missing {filepath}")
                        continue

                    data_paths[(symbol, timeframe)] = filepath

            if len(data_paths) == 0:
                print("Error: No CSV files found")
                sys.exit(1)

            backtester.load_all_data('csv', start_date, end_date, data_paths)

    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        sys.exit(1)

    # Run backtest
    try:
        logger.info("Running backtest...")
        backtester.run(check_interval_hours=args.interval)

    except KeyboardInterrupt:
        logger.warning("Backtest interrupted by user")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Analyze results
    logger.info("Analyzing results...")
    results = backtester.get_results()
    analyzer = PerformanceAnalyzer(results)

    # Print summary
    if not args.quiet:
        backtester.print_summary()

    # Generate report
    if args.report:
        logger.info(f"Generating report: {args.report}")
        analyzer.generate_report(args.report)

    # Export trades
    if args.trades:
        logger.info(f"Exporting trades: {args.trades}")
        analyzer.export_trades_to_csv(args.trades)

    # Export equity curve
    if args.equity:
        logger.info(f"Exporting equity curve: {args.equity}")
        analyzer.export_equity_curve_to_csv(args.equity)

    logger.info("Backtest completed successfully!")


if __name__ == '__main__':
    main()
