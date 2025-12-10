"""
Dollar Cost Averaging Example
Demonstrates how to use DCA strategies
"""

import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bot import MT5TradingBot
from src.utils import load_config, load_credentials, setup_logging
from src.dca import DCAConfig, DCAPositionManager, DCADirection, DCAType


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

    print("\n=== Dollar Cost Averaging Example ===\n")

    # Create DCA position manager
    dca_manager = DCAPositionManager()

    # Example 1: Fixed Size DCA
    print("1. Fixed Size DCA Strategy")
    print("-" * 40)

    # Get current price for EURUSD
    df = bot.collector.get_latest_data('EURUSD', 'H1', bars=100)
    if df is not None:
        current_price = df['close'].iloc[-1]
        print(f"Current EURUSD price: {current_price:.5f}")

        # Create DCA configuration
        dca_config = DCAConfig(
            symbol='EURUSD',
            direction=DCADirection.LONG,
            dca_type=DCAType.FIXED_SIZE,
            initial_size=0.1,
            dca_size=0.1,
            max_entries=5,
            max_total_size=0.5,
            stop_loss_percent=10.0,
            take_profit_percent=20.0,
            allow_averaging_down=True
        )

        # Create position
        position = dca_manager.create_position(
            config=dca_config,
            initial_price=current_price,
            timestamp=datetime.now()
        )

        print(f"\nInitial DCA Position Created:")
        print(f"  Symbol: {position.symbol}")
        print(f"  Direction: {position.direction.value}")
        print(f"  Initial Size: {position.total_size}")
        print(f"  Initial Price: {position.average_price:.5f}")

        # Simulate price drop and add DCA entries
        simulated_prices = [current_price * 0.99, current_price * 0.98, current_price * 0.97]

        for i, sim_price in enumerate(simulated_prices, 1):
            entry = dca_manager.update_position(
                symbol='EURUSD',
                current_price=sim_price,
                current_time=datetime.now()
            )

            if entry:
                print(f"\nDCA Entry #{entry.entry_id} added:")
                print(f"  Price: {entry.price:.5f}")
                print(f"  Size: {entry.size}")
                print(f"  Total Size: {position.total_size}")
                print(f"  Average Price: {position.average_price:.5f}")

        # Get position summary
        summary = dca_manager.get_position_summary('EURUSD', simulated_prices[-1])
        print(f"\n=== Position Summary ===")
        print(f"  Total Entries: {summary['num_entries']}")
        print(f"  Total Size: {summary['total_size']}")
        print(f"  Average Price: {summary['average_price']:.5f}")
        print(f"  Current Price: {summary['current_price']:.5f}")
        print(f"  Unrealized P&L: ${summary['unrealized_pnl']:.2f} ({summary['unrealized_pnl_percent']:.2f}%)")

    # Example 2: Grid DCA
    print("\n\n2. Grid-Based DCA Strategy")
    print("-" * 40)

    df_gbpusd = bot.collector.get_latest_data('GBPUSD', 'H1', bars=100)
    if df_gbpusd is not None:
        current_price_gbp = df_gbpusd['close'].iloc[-1]
        print(f"Current GBPUSD price: {current_price_gbp:.5f}")

        # Create grid DCA configuration
        grid_config = DCAConfig(
            symbol='GBPUSD',
            direction=DCADirection.LONG,
            dca_type=DCAType.GRID,
            initial_size=0.1,
            dca_size=0.1,
            max_entries=5,
            grid_spacing_percent=0.5,  # 0.5% spacing
            grid_start_price=current_price_gbp,
            max_total_size=0.6,
            stop_loss_percent=15.0,
            take_profit_percent=25.0
        )

        position_gbp = dca_manager.create_position(
            config=grid_config,
            initial_price=current_price_gbp,
            timestamp=datetime.now()
        )

        print(f"\nGrid DCA Position Created:")
        print(f"  Grid Levels:")

        from src.dca.dca_strategy import DCAStrategy
        strategy = DCAStrategy(grid_config)
        for i, level in enumerate(strategy.grid_levels, 1):
            print(f"    Level {i}: {level:.5f}")

    # Portfolio summary
    print("\n\n=== Portfolio Summary ===")
    print("-" * 40)

    prices = {
        'EURUSD': simulated_prices[-1] if df is not None else 0,
        'GBPUSD': current_price_gbp if df_gbpusd is not None else 0
    }

    portfolio = dca_manager.get_portfolio_summary(prices)
    print(f"Active Positions: {portfolio['num_active_positions']}")
    print(f"Total Unrealized P&L: ${portfolio['total_unrealized_pnl']:.2f} ({portfolio['total_unrealized_pnl_percent']:.2f}%)")
    print(f"Total Cost: ${portfolio['total_cost']:.2f}")

    # Stop bot
    bot.stop()
    print("\nDCA Example complete!")


if __name__ == "__main__":
    main()
