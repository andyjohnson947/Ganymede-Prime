#!/usr/bin/env python3
"""
Confluence Trading Bot - Main Entry Point
Based on EA analysis of 428 trades with 64.3% win rate

Supports dual-strategy mode:
- Confluence Strategy (H1 mean reversion with Grid/Hedge/DCA)
- Scalping Strategy (M1 momentum-based fast trades)

Usage:
    python main.py --login 12345 --password "yourpass" --server "Broker-Server"
    python main.py --gui  # Launch with GUI
    python main.py --scalping-only  # Run only scalping strategy
"""

import argparse
import sys
import threading
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import logger and other components
from core.mt5_manager import MT5Manager
from strategies.confluence_strategy import ConfluenceStrategy
from strategies.scalping_strategy import ScalpingStrategy
from utils.logger import logger
from config.strategy_config import SYMBOLS, SCALPING_ENABLED
import config.strategy_config as config


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

    parser.add_argument(
        '--scalping-only',
        action='store_true',
        help='Run only the scalping strategy (disables confluence strategy)'
    )

    parser.add_argument(
        '--no-scalping',
        action='store_true',
        help='Disable scalping even if SCALPING_ENABLED=True in config'
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()

    # Print banner
    print()
    print("=" * 80)
    print("     CONFLUENCE TRADING BOT")
    print("     Based on EA Reverse Engineering")
    print("=" * 80)
    print()
    print("Strategy Parameters (Discovered from 428 trades):")
    print("  • Win Rate: 64.3%")
    print("  • Minimum Confluence Score: 4")
    print("  • Grid Spacing: 10.8 pips")
    print("  • Hedge Trigger: 8 pips (2.4x ratio)")
    print("  • Risk Per Trade: 1%")
    print("  • Max Exposure: 5.04 lots")
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
        # Determine which strategies to run
        run_confluence = not args.scalping_only
        run_scalping = (SCALPING_ENABLED and not args.no_scalping) or args.scalping_only

        strategies_to_run = []
        threads = []

        # Initialize confluence strategy
        if run_confluence:
            confluence_strategy = ConfluenceStrategy(mt5_manager)
            strategies_to_run.append(('Confluence', confluence_strategy, symbols))

        # Initialize scalping strategy
        if run_scalping:
            scalping_config = {
                'SCALP_TIMEFRAME': config.SCALP_TIMEFRAME,
                'SCALP_LOT_SIZE': config.SCALP_LOT_SIZE,
                'SCALP_MAX_POSITIONS': config.SCALP_MAX_POSITIONS,
                'SCALP_MAX_POSITIONS_PER_SYMBOL': config.SCALP_MAX_POSITIONS_PER_SYMBOL,
                'SCALP_MOMENTUM_PERIOD': config.SCALP_MOMENTUM_PERIOD,
                'SCALP_VOLUME_SPIKE_THRESHOLD': config.SCALP_VOLUME_SPIKE_THRESHOLD,
                'SCALP_BREAKOUT_LOOKBACK': config.SCALP_BREAKOUT_LOOKBACK,
                'SCALP_BARS_TO_FETCH': config.SCALP_BARS_TO_FETCH,
                'SCALP_MAX_HOLD_MINUTES': config.SCALP_MAX_HOLD_MINUTES,
                'SCALP_USE_TRAILING_STOP': config.SCALP_USE_TRAILING_STOP,
                'SCALP_TRAILING_STOP_PIPS': config.SCALP_TRAILING_STOP_PIPS,
                'SCALP_TRADING_SESSIONS': config.SCALP_TRADING_SESSIONS,
                'SCALP_CHECK_INTERVAL_SECONDS': config.SCALP_CHECK_INTERVAL_SECONDS,
            }
            scalping_strategy = ScalpingStrategy(mt5_manager, scalping_config)
            strategies_to_run.append(('Scalping', scalping_strategy, symbols))

        if not strategies_to_run:
            print("❌ No strategies enabled!")
            sys.exit(1)

        # Display active strategies
        print(f"🚀 Active Strategies: {', '.join([s[0] for s in strategies_to_run])}")
        print()

        # If only one strategy, run directly
        if len(strategies_to_run) == 1:
            name, strategy, syms = strategies_to_run[0]
            logger.info(f"Starting {name} strategy with symbols: {syms}")
            strategy.start(syms)

        # If multiple strategies, run in separate threads
        else:
            print("📊 Running dual-strategy mode (Confluence + Scalping)")
            print("   Both strategies will operate independently")
            print()

            def run_strategy(name, strategy, syms):
                try:
                    logger.info(f"Starting {name} strategy in thread")
                    strategy.start(syms)
                except Exception as e:
                    logger.error(f"{name} strategy error: {e}")
                    import traceback
                    traceback.print_exc()

            # Start each strategy in its own thread
            for name, strategy, syms in strategies_to_run:
                thread = threading.Thread(
                    target=run_strategy,
                    args=(name, strategy, syms),
                    name=f"{name}Strategy",
                    daemon=True
                )
                thread.start()
                threads.append(thread)

            # Wait for all threads
            for thread in threads:
                thread.join()

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
