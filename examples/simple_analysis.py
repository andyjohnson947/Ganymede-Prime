"""
Simple Analysis Example
Demonstrates how to analyze a symbol
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

    # Start bot (connects to MT5)
    if not bot.start():
        print("Failed to connect to MT5")
        return

    # Analyze EURUSD
    print("\nAnalyzing EURUSD H1...")
    results = bot.analyze_symbol('EURUSD', 'H1')

    # Display results
    if 'error' not in results:
        print("\n=== Analysis Results ===")

        print("\nIndicators:")
        for name, value in results.get('indicators', {}).items():
            print(f"  {name}: {value:.5f}")

        print(f"\nPatterns: {len(results.get('patterns', []))}")
        for pattern in results.get('patterns', []):
            print(f"  - {pattern['name']} ({pattern['direction']})")

        if results.get('market_profile'):
            profile = results['market_profile']
            print(f"\nMarket Profile:")
            print(f"  VWAP: {profile['vwap']:.5f}")
            print(f"  POC:  {profile['poc']:.5f}")
            print(f"  VAH:  {profile['vah']:.5f}")
            print(f"  VAL:  {profile['val']:.5f}")
    else:
        print(f"Error: {results['error']}")

    # Stop bot
    bot.stop()
    print("\nAnalysis complete!")


if __name__ == "__main__":
    main()
