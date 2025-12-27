#!/usr/bin/env python3
"""
Export Historical Data from MT5 for Backtesting
Run this on a system with MT5 installed
"""

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import os
import sys

# Add credentials path
sys.path.insert(0, os.path.dirname(__file__))
from trading_bot.utils.credential_store import load_credentials


def export_data(symbol: str, timeframe_str: str, days: int, output_dir: str = "backtest_data"):
    """Export historical data to CSV"""

    # Map timeframe
    timeframe_map = {
        'H1': mt5.TIMEFRAME_H1,
        'D1': mt5.TIMEFRAME_D1,
        'W1': mt5.TIMEFRAME_W1
    }

    tf = timeframe_map.get(timeframe_str)
    if tf is None:
        print(f"Unknown timeframe: {timeframe_str}")
        return False

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    print(f"Exporting {symbol} {timeframe_str} from {start_date} to {end_date}")

    # Fetch data
    rates = mt5.copy_rates_range(symbol, tf, start_date, end_date)

    if rates is None or len(rates) == 0:
        print(f"Failed to fetch data for {symbol} {timeframe_str}")
        return False

    # Convert to DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Save to CSV
    filename = f"{output_dir}/{symbol}_{timeframe_str}.csv"
    df.to_csv(filename, index=False)

    print(f"✅ Exported {len(df)} bars to {filename}")
    return True


def main():
    # Load MT5 credentials
    creds = load_credentials()
    if not creds:
        print("❌ No MT5 credentials found. Run setup first.")
        return

    # Initialize MT5
    if not mt5.initialize():
        print(f"❌ MT5 initialize failed: {mt5.last_error()}")
        return

    # Login
    if not mt5.login(creds['login'], creds['password'], creds['server']):
        print(f"❌ MT5 login failed: {mt5.last_error()}")
        mt5.shutdown()
        return

    print(f"✅ Connected to MT5 - {creds['server']}")
    print()

    # Export data for backtesting (last 60 days)
    symbols = ['EURUSD', 'GBPUSD']
    timeframes = ['H1', 'D1', 'W1']

    # Lookback buffer (same as backtester)
    lookback_days = {
        'H1': 10 + 30,   # 10 buffer + 30 test period
        'D1': 60 + 30,   # 60 buffer + 30 test period
        'W1': 180 + 30   # 180 buffer + 30 test period
    }

    success_count = 0
    total_count = 0

    for symbol in symbols:
        for tf in timeframes:
            total_count += 1
            days = lookback_days.get(tf, 60)
            if export_data(symbol, tf, days):
                success_count += 1

    print()
    print(f"Export complete: {success_count}/{total_count} successful")

    # Shutdown
    mt5.shutdown()


if __name__ == "__main__":
    main()
