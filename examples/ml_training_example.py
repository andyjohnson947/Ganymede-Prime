"""
Machine Learning Training Example
Demonstrates how to train ML models with ROC, slope, and flow features
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bot import MT5TradingBot
from src.utils import load_config, load_credentials, setup_logging
from src.ml import MLModelTrainer


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

    print("\n=== Machine Learning Training Example ===\n")

    # Get data for training
    symbol = 'EURUSD'
    timeframe = 'H1'
    bars = 5000  # More data for better training

    print(f"Fetching {bars} bars of {symbol} {timeframe} data...")
    df = bot.collector.get_latest_data(symbol, timeframe, bars=bars)

    if df is None or df.empty:
        print("No data available")
        bot.stop()
        return

    print(f"Data loaded: {len(df)} bars")

    # Calculate indicators first
    print("\nCalculating technical indicators...")
    df = bot.indicator_manager.calculate_all(df)
    print(f"Indicators calculated: {len(bot.indicator_manager.get_indicator_names())}")

    # Initialize ML trainer
    print("\nInitializing ML models...")
    ml_config = config.get('machine_learning', {})
    trainer = MLModelTrainer(ml_config)

    # Prepare data
    print("\nEngineering features (ROC, slope, slope acceleration, flow data)...")
    X, y = trainer.prepare_data(df)

    print(f"\nFeatures engineered:")
    print(f"  Total samples: {len(X)}")
    print(f"  Total features: {len(X.columns)}")
    print(f"  Target distribution: Up={y.sum()}, Down={len(y)-y.sum()}")

    # Display some key features
    print(f"\nKey features created:")
    key_features = [col for col in X.columns if any(x in col for x in
                   ['roc', 'slope', 'volume', 'flow', 'acceleration'])][:10]
    for feature in key_features:
        print(f"  - {feature}")

    # Train models
    print("\n" + "="*50)
    print("Training ML Models...")
    print("="*50)

    results = trainer.train(X, y)

    # Display results
    print("\n=== Training Results ===\n")

    if 'random_forest' in results:
        rf = results['random_forest']
        print("Random Forest:")
        print(f"  Train Accuracy: {rf['train_accuracy']:.4f}")
        print(f"  Test Accuracy:  {rf['test_accuracy']:.4f}")
        print(f"  Precision:      {rf['precision']:.4f}")
        print(f"  Recall:         {rf['recall']:.4f}")
        print(f"  F1 Score:       {rf['f1_score']:.4f}")

    if 'gradient_boosting' in results:
        gb = results['gradient_boosting']
        print("\nGradient Boosting:")
        print(f"  Train Accuracy: {gb['train_accuracy']:.4f}")
        print(f"  Test Accuracy:  {gb['test_accuracy']:.4f}")
        print(f"  Precision:      {gb['precision']:.4f}")
        print(f"  Recall:         {gb['recall']:.4f}")
        print(f"  F1 Score:       {gb['f1_score']:.4f}")

    # Cross-validation results
    if 'cross_validation' in results:
        cv = results['cross_validation']
        print("\nCross-Validation:")
        if 'random_forest' in cv:
            print(f"  Random Forest: {cv['random_forest']['mean']:.4f} (+/- {cv['random_forest']['std']:.4f})")
        if 'gradient_boosting' in cv:
            print(f"  Gradient Boosting: {cv['gradient_boosting']['mean']:.4f} (+/- {cv['gradient_boosting']['std']:.4f})")

    # Feature importance
    if 'feature_importance' in results:
        importance = results['feature_importance']

        print("\n=== Top 15 Most Important Features ===\n")

        if 'random_forest' in importance:
            print("Random Forest:")
            for i, (feature, score) in enumerate(list(importance['random_forest'].items())[:15], 1):
                print(f"  {i:2d}. {feature:30s}: {score:.4f}")

        if 'gradient_boosting' in importance:
            print("\nGradient Boosting:")
            for i, (feature, score) in enumerate(list(importance['gradient_boosting'].items())[:15], 1):
                print(f"  {i:2d}. {feature:30s}: {score:.4f}")

    # Save models
    print("\n" + "="*50)
    print("Saving models...")
    trainer.save_models()
    print("Models saved successfully!")

    # Stop bot
    bot.stop()
    print("\nML Training Example complete!")


if __name__ == "__main__":
    main()
