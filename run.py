#!/usr/bin/env python3
"""
MT5 Trading Bot - One-Click Launcher
Main entry point for all bot operations
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.bot import MT5TradingBot
from src.utils import load_config, load_credentials, setup_logging


def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def setup_credentials():
    """Launch GUI for credentials setup"""
    print_header("MT5 Credentials Setup")

    try:
        from src.gui.account_setup import AccountSetupGUI
        app = AccountSetupGUI()
        app.run()
    except Exception as e:
        print(f"❌ Error launching GUI: {e}")
        print("\nManual setup:")
        print("1. Copy config/mt5_credentials.example.yaml")
        print("2. Rename to config/mt5_credentials.yaml")
        print("3. Edit with your MT5 credentials")
        sys.exit(1)


def run_bot():
    """Run the bot in continuous mode"""
    print_header("Starting MT5 Trading Bot")

    config = load_config()
    credentials = load_credentials()
    logger = setup_logging(config)

    bot = MT5TradingBot(config, credentials)

    if not bot.start():
        print("❌ Failed to start bot")
        sys.exit(1)

    # Display status
    status = bot.get_status()
    print(f"✅ Bot started successfully!")
    print(f"\nAccount: {status.get('account', {}).get('login', 'N/A')}")
    print(f"Server:  {status.get('account', {}).get('server', 'N/A')}")
    print(f"Balance: ${status.get('account', {}).get('balance', 0):,.2f}")

    print("\n📊 Bot is running...")
    print("   • Collecting data every 5 minutes")
    print("   • Saving daily profiles at 23:55 UTC")
    print("   • Press Ctrl+C to stop\n")

    try:
        import time
        while bot.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping bot...")

    bot.stop()
    print("✅ Bot stopped successfully")


def analyze_symbol(symbol, timeframe):
    """Analyze a specific symbol"""
    print_header(f"Analyzing {symbol} {timeframe}")

    config = load_config()
    credentials = load_credentials()
    logger = setup_logging(config)

    bot = MT5TradingBot(config, credentials)

    if not bot.start():
        print("❌ Failed to connect to MT5")
        sys.exit(1)

    # Perform analysis
    results = bot.analyze_symbol(symbol, timeframe)

    if 'error' in results:
        print(f"❌ Analysis failed: {results['error']}")
        bot.stop()
        sys.exit(1)

    # Display results
    print(f"📈 Analysis Results:")
    print(f"   Symbol:    {symbol}")
    print(f"   Timeframe: {timeframe}")
    print(f"   Time:      {results['timestamp']}")

    if 'indicators' in results and results['indicators']:
        print(f"\n📊 Technical Indicators:")
        for name, value in list(results['indicators'].items())[:10]:
            print(f"   {name:20s}: {value:.5f}")

    if 'patterns' in results and results['patterns']:
        print(f"\n🔍 Patterns Detected: {len(results['patterns'])}")
        for pattern in results['patterns'][:5]:
            print(f"   • {pattern['name']}: {pattern['direction']} "
                  f"(confidence: {pattern['confidence']:.0%})")

    if 'market_profile' in results and results['market_profile']:
        profile = results['market_profile']
        print(f"\n📍 Market Profile:")
        print(f"   VWAP: {profile['vwap']:.5f}")
        print(f"   POC:  {profile['poc']:.5f}")
        print(f"   VAH:  {profile['vah']:.5f}")
        print(f"   VAL:  {profile['val']:.5f}")

    bot.stop()
    print("\n✅ Analysis complete!")


def train_ml_models():
    """Train machine learning models"""
    print_header("Training ML Models")

    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "examples/ml_training_example.py"],
            check=True
        )
    except subprocess.CalledProcessError:
        print("❌ Training failed")
        sys.exit(1)


def run_ml_predictions():
    """Run ML predictions"""
    print_header("ML Predictions")

    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "examples/ml_prediction_example.py"],
            check=True
        )
    except subprocess.CalledProcessError:
        print("❌ Prediction failed")
        sys.exit(1)


def run_dca_demo():
    """Run DCA demonstration"""
    print_header("DCA Strategy Demo")

    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "examples/dca_example.py"],
            check=True
        )
    except subprocess.CalledProcessError:
        print("❌ DCA demo failed")
        sys.exit(1)


def run_ea_mining():
    """Run EA reverse engineering"""
    print_header("EA Reverse Engineering")

    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "reverse_engineer_ea.py"],
            check=True
        )
    except subprocess.CalledProcessError:
        print("❌ EA mining failed")
        sys.exit(1)


def collect_data():
    """Collect data only"""
    print_header("Data Collection")

    config = load_config()
    credentials = load_credentials()
    logger = setup_logging(config)

    bot = MT5TradingBot(config, credentials)

    if not bot.start():
        print("❌ Failed to connect to MT5")
        sys.exit(1)

    print("📥 Collecting data...")
    results = bot.collector.collect_all_data()

    print(f"\n✅ Data collection complete!")
    print(f"   Symbols: {len(results['price_data'])}")
    if results['orders'] is not None:
        print(f"   Orders:  {len(results['orders'])}")
    if results['deals'] is not None:
        print(f"   Deals:   {len(results['deals'])}")

    bot.stop()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='MT5 Trading Bot - One-Click Launcher',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                          Run the bot
  python run.py --setup                  Setup MT5 credentials
  python run.py --analyze EURUSD         Analyze EURUSD
  python run.py --analyze GBPUSD --tf H4 Analyze GBPUSD H4
  python run.py --train                  Train ML models
  python run.py --predict                Run ML predictions
  python run.py --dca-demo               Run DCA demo
  python run.py --mine-ea                Reverse engineer your EA
  python run.py --collect                Collect data only
        """
    )

    parser.add_argument('--setup', action='store_true',
                       help='Setup MT5 credentials (GUI)')
    parser.add_argument('--analyze', metavar='SYMBOL',
                       help='Analyze a specific symbol')
    parser.add_argument('--tf', '--timeframe', default='H1',
                       help='Timeframe for analysis (default: H1)')
    parser.add_argument('--train', action='store_true',
                       help='Train ML models')
    parser.add_argument('--predict', action='store_true',
                       help='Run ML predictions')
    parser.add_argument('--dca-demo', action='store_true',
                       help='Run DCA strategy demo')
    parser.add_argument('--mine-ea', action='store_true',
                       help='Reverse engineer and improve existing EA')
    parser.add_argument('--collect', action='store_true',
                       help='Collect data only')

    args = parser.parse_args()

    try:
        # Handle different modes
        if args.setup:
            setup_credentials()

        elif args.analyze:
            analyze_symbol(args.analyze, args.tf)

        elif args.train:
            train_ml_models()

        elif args.predict:
            run_ml_predictions()

        elif args.dca_demo:
            run_dca_demo()

        elif args.mine_ea:
            run_ea_mining()

        elif args.collect:
            collect_data()

        else:
            # Default: run the bot
            run_bot()

    except FileNotFoundError as e:
        print(f"\n❌ Configuration Error: {e}")
        print("\n💡 Run setup first: python run.py --setup")
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⏹️  Cancelled by user")
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
