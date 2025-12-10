"""
Machine Learning Prediction Example
Demonstrates how to use trained ML models for predictions
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bot import MT5TradingBot
from src.utils import load_config, load_credentials, setup_logging
from src.ml import MLModelTrainer, MLPredictor


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

    print("\n=== Machine Learning Prediction Example ===\n")

    # Initialize ML trainer and load models
    print("Loading trained models...")
    ml_config = config.get('machine_learning', {})
    trainer = MLModelTrainer(ml_config)

    try:
        trainer.load_models()
        print("Models loaded successfully!")
    except Exception as e:
        print(f"Error loading models: {e}")
        print("\nPlease train models first using: python examples/ml_training_example.py")
        bot.stop()
        return

    # Create predictor
    predictor = MLPredictor(trainer)

    # Get current data
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY']

    print("\n" + "="*60)
    print("Generating Predictions for Current Market")
    print("="*60)

    for symbol in symbols:
        print(f"\n{symbol}:")
        print("-" * 40)

        # Get recent data
        df = bot.collector.get_latest_data(symbol, 'H1', bars=200)

        if df is None or df.empty:
            print(f"  No data available")
            continue

        # Calculate indicators
        df = bot.indicator_manager.calculate_all(df)

        # Get prediction
        signal, confidence, details = predictor.predict(df)

        # Display result
        signal_map = {1: 'BUY 📈', -1: 'SELL 📉', 0: 'HOLD ⏸️'}
        signal_str = signal_map.get(signal, 'UNKNOWN')

        print(f"  Current Price: {df['close'].iloc[-1]:.5f}")
        print(f"  Signal:        {signal_str}")
        print(f"  Confidence:    {confidence:.1%}")
        print(f"  Model:         {details['model_type']}")
        print(f"\n  Probabilities:")
        print(f"    Up (Buy):    {details['probabilities']['up']:.1%}")
        print(f"    Down (Sell): {details['probabilities']['down']:.1%}")

        # Additional analysis
        if signal != 0:
            # Get recent indicators
            rsi = df['RSI_14'].iloc[-1] if 'RSI_14' in df.columns else None
            macd = df['MACD'].iloc[-1] if 'MACD' in df.columns else None

            print(f"\n  Technical Context:")
            if rsi is not None:
                print(f"    RSI:         {rsi:.2f}")
            if macd is not None:
                print(f"    MACD:        {macd:.5f}")

    # Batch prediction example
    print("\n\n" + "="*60)
    print("Batch Prediction Example (EURUSD)")
    print("="*60)

    df_eurusd = bot.collector.get_latest_data('EURUSD', 'H1', bars=500)
    if df_eurusd is not None:
        # Calculate indicators
        df_eurusd = bot.indicator_manager.calculate_all(df_eurusd)

        # Generate batch predictions
        print("\nGenerating predictions for last 50 bars...")
        df_with_predictions = predictor.batch_predict(df_eurusd, lookback=100)

        # Show recent predictions
        recent = df_with_predictions.tail(10)

        print("\nRecent Predictions:")
        print("-" * 60)
        print(f"{'Time':<20} {'Close':<10} {'Signal':<8} {'Confidence':<12}")
        print("-" * 60)

        for idx, row in recent.iterrows():
            signal_str = {1: 'BUY', -1: 'SELL', 0: 'HOLD'}.get(row['ml_signal'], 'UNKNOWN')
            print(f"{str(idx):<20} {row['close']:<10.5f} {signal_str:<8} {row['ml_confidence']:<12.1%}")

        # Calculate prediction accuracy (if we have future data)
        print("\n=== Prediction Statistics ===")
        predictions = df_with_predictions['ml_signal'].tail(50)
        buy_signals = (predictions == 1).sum()
        sell_signals = (predictions == -1).sum()
        hold_signals = (predictions == 0).sum()

        print(f"\nLast 50 bars:")
        print(f"  Buy signals:  {buy_signals} ({buy_signals/50:.1%})")
        print(f"  Sell signals: {sell_signals} ({sell_signals/50:.1%})")
        print(f"  Hold signals: {hold_signals} ({hold_signals/50:.1%})")

    # Stop bot
    bot.stop()
    print("\nML Prediction Example complete!")


if __name__ == "__main__":
    main()
