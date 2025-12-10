"""
Data Collection Example
Demonstrates how to collect and store MT5 data
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bot import MT5TradingBot
from src.utils import load_config, load_credentials, setup_logging


def main():
    # Load configuration
    config = load_config()
    credentials = load_credentials()

    # Setup logging
    logger = setup_logging(config)

    # Create bot
    bot = MT5TradingBot(config, credentials)

    # Start bot
    if not bot.start():
        print("Failed to connect to MT5")
        return

    print("\n=== Data Collection ===")

    # Collect all configured data
    print("\nCollecting historical data...")
    results = bot.collector.collect_all_data()

    # Display summary
    print(f"\nData Collection Summary:")
    print(f"  Symbols processed: {len(results['price_data'])}")

    for symbol, timeframes in results['price_data'].items():
        print(f"\n  {symbol}:")
        for tf, df in timeframes.items():
            print(f"    {tf}: {len(df)} bars")

    if results['orders'] is not None:
        print(f"\n  Historical orders: {len(results['orders'])}")

    if results['deals'] is not None:
        print(f"  Historical deals: {len(results['deals'])}")

    if results['errors']:
        print(f"\n  Errors: {results['errors']}")

    # Stop bot
    bot.stop()
    print("\nData collection complete!")


if __name__ == "__main__":
    main()
