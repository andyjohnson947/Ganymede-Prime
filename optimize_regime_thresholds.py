#!/usr/bin/env python3
"""
Regime Threshold Optimizer - Find Sweet Spot

Analyzes your trading history to find optimal thresholds for:
- Hurst alone vs Hurst+VHF vs Hurst+VHF+ADX
- Different threshold values
- Measures which combination best predicts wins vs losses

Usage:
    python optimize_regime_thresholds.py --symbols GBPUSD --days 30
    python optimize_regime_thresholds.py --symbols EURUSD GBPUSD --days 60 --login 12345 --password "pass" --server "Broker"
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent / 'trading_bot'))

from core.mt5_manager import MT5Manager
from diagnostics.data_store import DataStore
from diagnostics.regime_optimizer import RegimeOptimizer


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Find optimal regime detection thresholds'
    )

    parser.add_argument(
        '--symbols',
        type=str,
        nargs='+',
        default=['GBPUSD'],
        help='Symbols to analyze (default: GBPUSD)'
    )

    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days to analyze (default: 30)'
    )

    parser.add_argument(
        '--min-trades',
        type=int,
        default=10,
        help='Minimum trades per regime for significance (default: 10)'
    )

    parser.add_argument(
        '--login',
        type=int,
        required=True,
        help='MT5 account login'
    )

    parser.add_argument(
        '--password',
        type=str,
        required=True,
        help='MT5 account password'
    )

    parser.add_argument(
        '--server',
        type=str,
        required=True,
        help='MT5 server name'
    )

    parser.add_argument(
        '--data-dir',
        type=str,
        default='data/diagnostics',
        help='Directory containing diagnostic data (default: data/diagnostics)'
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()

    print("=" * 80)
    print("     REGIME THRESHOLD OPTIMIZER")
    print("=" * 80)
    print()
    print("Finding sweet spot for regime detection...")
    print(f"Symbols: {', '.join(args.symbols)}")
    print(f"Period: {args.days} days")
    print()
    print("=" * 80)
    print()

    # Connect to MT5
    print("🔌 Connecting to MT5...")
    mt5_manager = MT5Manager(
        login=args.login,
        password=args.password,
        server=args.server
    )

    if not mt5_manager.connect():
        print("❌ Failed to connect to MT5")
        sys.exit(1)

    print("✅ MT5 Connected\n")

    # Initialize data store
    data_store = DataStore(args.data_dir)

    # Create optimizer
    optimizer = RegimeOptimizer(mt5_manager, data_store)

    try:
        # Run optimization
        results = optimizer.optimize_thresholds(
            symbols=args.symbols,
            days=args.days,
            min_trades_per_regime=args.min_trades
        )

        # Print results
        optimizer.print_results(results)

        print("✅ Optimization complete\n")

    except Exception as e:
        print(f"\n❌ Error during optimization: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        mt5_manager.disconnect()


if __name__ == "__main__":
    main()
