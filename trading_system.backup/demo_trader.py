#!/usr/bin/env python3
"""
Demo Trading Script
Tests the trading system on a demo MT5 account
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import signal
from datetime import datetime

from trade_manager import TradeManager
import trading_config as config
from src.utils import load_credentials


class DemoTrader:
    """Demo trading application"""

    def __init__(self):
        self.trade_manager = None
        self.running = False

    def setup(self):
        """Setup trading system"""
        print("\n" + "=" * 80)
        print("  DEMO TRADING SYSTEM - EA REVERSE ENGINEERED STRATEGY")
        print("=" * 80)
        print()

        # Load MT5 credentials
        print("Loading MT5 credentials...")
        try:
            credentials = load_credentials()
            mt5_creds = credentials.get('mt5', {})

            login = mt5_creds.get('login')
            password = mt5_creds.get('password')
            server = mt5_creds.get('server')

            if not all([login, password, server]):
                print("❌ MT5 credentials not configured!")
                print("   Please run: python EASY_START.py")
                print("   And choose option 5: Setup MT5 Credentials")
                return False

        except Exception as e:
            print(f"❌ Error loading credentials: {e}")
            return False

        # Create trade manager
        print(f"Initializing trade manager for {config.DEFAULT_SYMBOL}...")
        self.trade_manager = TradeManager(
            symbol=config.DEFAULT_SYMBOL,
            initial_balance=config.INITIAL_BALANCE
        )

        # Connect to MT5
        print(f"Connecting to MT5: {server}...")
        if not self.trade_manager.connect_mt5(login, password, server):
            print("❌ Failed to connect to MT5")
            return False

        print("✅ Connected to MT5 successfully!")
        print()

        # Print configuration
        self.print_configuration()

        return True

    def print_configuration(self):
        """Print trading configuration"""
        print("📋 TRADING CONFIGURATION")
        print("-" * 80)
        print(f"Symbol: {config.DEFAULT_SYMBOL}")
        print(f"Initial Balance: ${config.INITIAL_BALANCE:,.2f}")
        print()

        print("Grid Settings:")
        print(f"  Spacing: {config.GRID_SPACING_PIPS} pips")
        print(f"  Max Levels: {config.MAX_GRID_LEVELS}")
        print(f"  Base Lot Size: {config.GRID_BASE_LOT_SIZE}")
        print()

        print("Hedge Settings:")
        print(f"  Enabled: {'✅' if config.HEDGE_ENABLED else '❌'}")
        print(f"  Ratio: {config.HEDGE_RATIO}x")
        print(f"  Trigger: {config.HEDGE_TRIGGER_PIPS} pips underwater")
        print()

        print("Recovery Settings:")
        print(f"  Enabled: {'✅' if config.RECOVERY_ENABLED else '❌'}")
        print(f"  Max Levels: {config.MAX_RECOVERY_LEVELS}")
        print(f"  Multiplier: {config.MARTINGALE_MULTIPLIER}x")
        print()

        print("Risk Management:")
        print(f"  Max Drawdown: {config.MAX_DRAWDOWN_PCT}%")
        print(f"  Daily Loss Limit: {config.MAX_DAILY_LOSS_PCT}%")
        print(f"  Max Consecutive Losses: {config.MAX_CONSECUTIVE_LOSSES}")
        print()

        print("Confluence Requirements:")
        print(f"  Minimum Score: {config.MIN_CONFLUENCE_SCORE} factors")
        print(f"  High Confidence: {config.HIGH_CONFIDENCE_SCORE}+ factors")
        print()

        print("=" * 80)
        print()

    def run(self, interval_seconds: int = 60):
        """
        Run trading loop

        Args:
            interval_seconds: How often to check for signals (60 = every minute)
        """
        self.running = True

        print("🚀 Starting trading loop...")
        print(f"⏱️  Checking for signals every {interval_seconds} seconds")
        print("Press Ctrl+C to stop")
        print()

        cycle_count = 0

        try:
            while self.running:
                cycle_count += 1
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                print(f"\n[{current_time}] Cycle #{cycle_count}")
                print("-" * 80)

                # Run trading cycle
                self.trade_manager.run_trading_cycle()

                # Print status
                self.trade_manager.print_status()

                # Wait for next cycle
                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("\n\n⚠️ Stopping trading system...")
            self.stop()

    def stop(self):
        """Stop trading system"""
        self.running = False

        if self.trade_manager:
            # Close all open positions
            open_positions = [p for p in self.trade_manager.positions if p.is_open]

            if open_positions:
                print(f"\n📊 Closing {len(open_positions)} open positions...")
                for position in open_positions:
                    self.trade_manager.close_position(position)

            # Disconnect from MT5
            self.trade_manager.disconnect_mt5()

        print("\n✅ Trading system stopped")
        print()

        # Print final statistics
        self.print_final_stats()

    def print_final_stats(self):
        """Print final trading statistics"""
        if not self.trade_manager:
            return

        print("\n" + "=" * 80)
        print("FINAL STATISTICS")
        print("=" * 80)

        closed_positions = [p for p in self.trade_manager.positions if not p.is_open]

        if not closed_positions:
            print("No trades executed")
            return

        total_trades = len(closed_positions)
        winning_trades = len([p for p in closed_positions if p.profit > 0])
        losing_trades = len([p for p in closed_positions if p.profit < 0])

        total_profit = sum(p.profit for p in closed_positions)
        avg_profit = total_profit / total_trades if total_trades > 0 else 0
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        print(f"Total Trades: {total_trades}")
        print(f"Winning Trades: {winning_trades}")
        print(f"Losing Trades: {losing_trades}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Total Profit/Loss: ${total_profit:.2f}")
        print(f"Average P/L per Trade: ${avg_profit:.2f}")
        print()

        # Risk metrics
        risk_status = self.trade_manager.risk_manager.get_risk_status()
        print(f"Final Balance: ${risk_status['current_balance']:,.2f}")
        print(f"Peak Balance: ${risk_status['peak_balance']:,.2f}")
        print(f"Max Drawdown: {risk_status['drawdown_pct']:.2f}%")
        print(f"Consecutive Losses: {risk_status['consecutive_losses']}")
        print()

        print("=" * 80)


def main():
    """Main entry point"""
    trader = DemoTrader()

    # Setup signal handler for clean shutdown
    def signal_handler(sig, frame):
        print("\n\n⚠️ Signal received - shutting down...")
        trader.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Setup and run
    if trader.setup():
        # Run with 60-second intervals (check every minute)
        trader.run(interval_seconds=60)
    else:
        print("\n❌ Setup failed - exiting")
        sys.exit(1)


if __name__ == "__main__":
    main()
