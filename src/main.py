"""
Main Entry Point for MT5 Trading Bot
"""

import sys
import signal
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bot import MT5TradingBot
from src.utils import load_config, load_credentials, setup_logging


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("\nShutdown signal received. Stopping bot...")
    sys.exit(0)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='MT5 Strategy Reversal Trading Bot')
    parser.add_argument(
        '--config',
        default='config/config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--credentials',
        default='config/mt5_credentials.yaml',
        help='Path to MT5 credentials file'
    )
    parser.add_argument(
        '--mode',
        choices=['run', 'analyze', 'backtest', 'collect'],
        default='run',
        help='Operating mode'
    )
    parser.add_argument(
        '--symbol',
        help='Symbol to analyze/backtest (for analyze and backtest modes)'
    )
    parser.add_argument(
        '--timeframe',
        default='H1',
        help='Timeframe (default: H1)'
    )

    args = parser.parse_args()

    # Load configuration
    try:
        config = load_config(args.config)
        credentials = load_credentials(args.credentials)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nTo configure MT5 credentials, run:")
        print("  python src/gui/account_setup.py")
        sys.exit(1)

    # Setup logging
    logger = setup_logging(config)
    logger.info("=" * 60)
    logger.info("MT5 Strategy Reversal Trading Bot")
    logger.info("=" * 60)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize bot
    bot = MT5TradingBot(config, credentials)

    try:
        if args.mode == 'run':
            # Normal operation mode
            logger.info("Starting bot in normal operation mode...")

            if not bot.start():
                logger.error("Failed to start bot")
                sys.exit(1)

            # Display status
            status = bot.get_status()
            logger.info(f"Bot Status: {status}")

            # Keep running
            logger.info("Bot is running. Press Ctrl+C to stop.")
            try:
                import time
                while bot.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")

            bot.stop()

        elif args.mode == 'analyze':
            # Analysis mode
            if not args.symbol:
                print("Error: --symbol required for analyze mode")
                sys.exit(1)

            logger.info(f"Starting analysis mode for {args.symbol}...")

            if not bot.start():
                logger.error("Failed to start bot")
                sys.exit(1)

            # Perform analysis
            results = bot.analyze_symbol(args.symbol, args.timeframe)

            # Display results
            print(f"\nAnalysis Results for {args.symbol} {args.timeframe}")
            print("=" * 60)

            if 'indicators' in results:
                print("\nIndicators:")
                for name, value in results['indicators'].items():
                    print(f"  {name}: {value:.5f}")

            if 'patterns' in results:
                print(f"\nPatterns Detected: {len(results['patterns'])}")
                for pattern in results['patterns']:
                    print(f"  - {pattern['name']}: {pattern['direction']} "
                          f"(confidence: {pattern['confidence']:.2f})")

            if 'market_profile' in results and results['market_profile']:
                profile = results['market_profile']
                print(f"\nMarket Profile:")
                print(f"  VWAP: {profile['vwap']:.5f}")
                print(f"  POC:  {profile['poc']:.5f}")
                print(f"  VAH:  {profile['vah']:.5f}")
                print(f"  VAL:  {profile['val']:.5f}")

            if 'hypothesis_tests' in results:
                print(f"\nHypothesis Tests:")
                for test in results['hypothesis_tests']:
                    print(f"  - {test['test_name']}: {test['result']} "
                          f"(p={test['p_value']:.4f})")

            bot.stop()

        elif args.mode == 'backtest':
            # Backtest mode
            if not args.symbol:
                print("Error: --symbol required for backtest mode")
                sys.exit(1)

            logger.info(f"Starting backtest mode for {args.symbol}...")

            if not bot.start():
                logger.error("Failed to start bot")
                sys.exit(1)

            # Run backtest
            results = bot.run_backtest(args.symbol, args.timeframe)

            if 'error' in results:
                print(f"Error: {results['error']}")
            else:
                print(bot.backtest_engine.get_results_summary(results))

            bot.stop()

        elif args.mode == 'collect':
            # Data collection mode
            logger.info("Starting data collection mode...")

            if not bot.start():
                logger.error("Failed to start bot")
                sys.exit(1)

            # Collect data
            logger.info("Collecting all data...")
            bot.collector.collect_all_data()
            logger.info("Data collection completed")

            bot.stop()

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)

    logger.info("Bot shutdown complete")


if __name__ == "__main__":
    main()
