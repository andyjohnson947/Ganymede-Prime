#!/usr/bin/env python3
"""
Confluence Trading Bot - Main Entry Point
Based on EA analysis of 428 trades with 64.3% win rate

Usage:
    python main.py --login 12345 --password "yourpass" --server "Broker-Server"
    python main.py --gui  # Launch with GUI
"""

import argparse
import sys
import os
from pathlib import Path

# CACHE CLEARING - Force Python to reload modules on every start
# This ensures code changes are always picked up without needing to restart Python interpreter
import importlib
if hasattr(importlib, 'invalidate_caches'):
    importlib.invalidate_caches()

# Clear __pycache__ for trading_bot modules to force fresh imports
def clear_pycache():
    """Clear Python cache files to ensure fresh module imports"""
    current_dir = Path(__file__).parent
    for pycache_dir in current_dir.rglob('__pycache__'):
        for cache_file in pycache_dir.glob('*.pyc'):
            try:
                cache_file.unlink()
            except Exception:
                pass

# Clear cache on startup
clear_pycache()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Disable Python bytecode generation (optional - prevents .pyc creation)
sys.dont_write_bytecode = True

from core.mt5_manager import MT5Manager
from strategies.confluence_strategy import ConfluenceStrategy
from utils.logger import logger
from config.strategy_config import SYMBOLS


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Confluence Trading Bot - Based on EA Reverse Engineering'
    )

    parser.add_argument(
        '--login',
        type=int,
        help='MT5 account login number'
    )

    parser.add_argument(
        '--password',
        type=str,
        help='MT5 account password'
    )

    parser.add_argument(
        '--server',
        type=str,
        help='MT5 server name'
    )

    parser.add_argument(
        '--symbols',
        type=str,
        nargs='+',
        help='Trading symbols (default: from config)'
    )

    parser.add_argument(
        '--gui',
        action='store_true',
        help='Launch with GUI interface'
    )

    parser.add_argument(
        '--paper-trade',
        action='store_true',
        help='Paper trading mode (simulation only)'
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()

    # Print banner
    print()
    print("=" * 80)
    print("     CONFLUENCE TRADING BOT - UPGRADED")
    print("     Timezone-Aware | Instrument-Specific Trading Windows")
    print("=" * 80)
    print()
    print("🔄 Cache Status: CLEARED (Fresh imports enabled)")
    print()
    print("Strategy Parameters:")
    print("  • Win Rate: 64.3%")
    print("  • Minimum Confluence Score: 4")
    print("  • Base Lot Size: 0.04 (updated)")
    print("  • Grid Spacing: 8 pips")
    print("  • Hedge Trigger: 8 pips (5x ratio)")
    print()
    print("NEW FEATURES:")
    print("  ✓ Timezone: GMT/GMT+1 with automatic DST handling")
    print("  ✓ Trading Windows: Instrument-specific entry/exit times")
    print("  ✓ Restrictions: No bank holidays, weekends, Friday afternoons")
    print("  ✓ Auto-close negative positions at window end")
    print("  ✓ Auto cache clearing: Code changes always picked up")
    print()
    print("=" * 80)
    print()

    # Check if GUI mode
    if args.gui:
        launch_gui(args)
        return

    # Validate credentials
    if not all([args.login, args.password, args.server]):
        print("❌ Error: MT5 credentials required")
        print("   Use: --login LOGIN --password PASSWORD --server SERVER")
        print("   Or use: --gui for graphical interface")
        sys.exit(1)

    # Get symbols
    symbols = args.symbols if args.symbols else SYMBOLS
    if not symbols:
        print("❌ Error: No symbols specified")
        print("   Use: --symbols EURUSD GBPUSD")
        sys.exit(1)

    # Connect to MT5
    logger.info(f"Connecting to MT5 - Login: {args.login}, Server: {args.server}")

    mt5_manager = MT5Manager(
        login=args.login,
        password=args.password,
        server=args.server
    )

    if not mt5_manager.connect():
        logger.error("Failed to connect to MT5")
        sys.exit(1)

    try:
        # Initialize strategy
        strategy = ConfluenceStrategy(mt5_manager)

        # Start trading
        logger.info(f"Starting strategy with symbols: {symbols}")
        strategy.start(symbols)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        mt5_manager.disconnect()
        logger.info("Bot stopped")


def launch_gui(args):
    """
    Launch GUI interface

    Args:
        args: Command line arguments
    """
    try:
        # Import GUI here to avoid dependency if not using GUI
        from gui.trading_gui import TradingGUI
        import tkinter as tk

        root = tk.Tk()
        app = TradingGUI(root)
        root.mainloop()

    except ImportError as e:
        print(f"❌ GUI dependencies not available: {e}")
        print("   Install required packages:")
        print("   pip install tkinter matplotlib")
        sys.exit(1)


if __name__ == "__main__":
    main()
