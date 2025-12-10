"""
Pattern Detection Example
Demonstrates pattern recognition capabilities
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

    print("\n=== Pattern Detection ===")

    # Get symbols from config
    symbols = config.get('trading', {}).get('symbols', ['EURUSD'])

    for symbol in symbols:
        print(f"\nAnalyzing {symbol}...")

        # Get data
        df = bot.collector.get_latest_data(symbol, 'H1', bars=500)

        if df is not None:
            # Detect patterns
            patterns = bot.pattern_detector.detect(df)

            print(f"  Detected {len(patterns)} patterns:")

            for pattern in patterns[-10:]:  # Show last 10
                print(f"    - {pattern.pattern_name}: {pattern.direction} "
                      f"(confidence: {pattern.confidence:.2f}) "
                      f"at {pattern.end_time}")

                # Store pattern in database
                bot.storage.store_pattern_detection(
                    symbol=symbol,
                    timeframe='H1',
                    pattern_name=pattern.pattern_name,
                    detection_time=pattern.end_time,
                    confidence=pattern.confidence,
                    direction=pattern.direction
                )
        else:
            print(f"  No data available for {symbol}")

    # Stop bot
    bot.stop()
    print("\nPattern detection complete!")


if __name__ == "__main__":
    main()
