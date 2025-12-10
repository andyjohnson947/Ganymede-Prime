#!/usr/bin/env python3
"""
Ganymede Trade City Backtesting Tool
Test strategy parameters on historical data across multiple pairs
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict
import json

from backtest_engine import BacktestEngine, BacktestResults
import trading_config as config


class BacktestDataLoader:
    """Loads historical data from MT5 for backtesting"""

    def __init__(self):
        self.mt5_connected = False

    def connect_mt5(self) -> bool:
        """Connect to MT5 for data access"""
        if not mt5.initialize():
            print(f"[ERROR] MT5 initialization failed: {mt5.last_error()}")
            print("[INFO] Make sure MetaTrader 5 terminal is running")
            return False

        self.mt5_connected = True
        print("[INFO] Connected to MT5 for data access")
        return True

    def disconnect_mt5(self):
        """Disconnect from MT5"""
        if self.mt5_connected:
            mt5.shutdown()
            self.mt5_connected = False

    def load_historical_data(self, symbol: str, timeframe: str,
                            days: int = 90) -> pd.DataFrame:
        """
        Load historical data from MT5

        Args:
            symbol: Trading symbol (e.g., 'EURUSD')
            timeframe: Timeframe ('M15', 'H1', 'H4', 'D1')
            days: Number of days to load

        Returns:
            DataFrame with OHLCV data
        """
        if not self.mt5_connected:
            print("[ERROR] Not connected to MT5")
            return pd.DataFrame()

        # Map timeframe string to MT5 constant
        timeframe_map = {
            'M1': mt5.TIMEFRAME_M1,
            'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15,
            'M30': mt5.TIMEFRAME_M30,
            'H1': mt5.TIMEFRAME_H1,
            'H4': mt5.TIMEFRAME_H4,
            'D1': mt5.TIMEFRAME_D1,
        }

        tf = timeframe_map.get(timeframe, mt5.TIMEFRAME_M15)

        # Calculate bars needed
        bars_per_day = {
            mt5.TIMEFRAME_M15: 96,
            mt5.TIMEFRAME_M30: 48,
            mt5.TIMEFRAME_H1: 24,
            mt5.TIMEFRAME_H4: 6,
            mt5.TIMEFRAME_D1: 1,
        }

        total_bars = bars_per_day.get(tf, 96) * days

        print(f"[INFO] Loading {days} days of {timeframe} data for {symbol}...")

        # Fetch data
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, total_bars)

        if rates is None or len(rates) == 0:
            print(f"[ERROR] Failed to get data for {symbol}: {mt5.last_error()}")
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)

        # Calculate VWAP
        df['VWAP'] = (df['close'] * df['tick_volume']).cumsum() / df['tick_volume'].cumsum()

        print(f"[INFO] Loaded {len(df)} bars for {symbol}")
        print(f"       Period: {df.index[0]} to {df.index[-1]}")

        return df


class BacktestReporter:
    """Generates backtest reports and comparisons"""

    @staticmethod
    def print_summary(results: BacktestResults):
        """Print detailed backtest summary"""
        print(f"\n{'='*80}")
        print(f"BACKTEST RESULTS - {results.symbol}")
        print(f"{'='*80}")
        print(f"Period: {results.start_date.strftime('%Y-%m-%d')} to {results.end_date.strftime('%Y-%m-%d')}")
        print(f"\nAccount Performance:")
        print(f"  Initial Balance:  ${results.initial_balance:,.2f}")
        print(f"  Final Balance:    ${results.final_balance:,.2f}")
        print(f"  Net Profit:       ${results.final_balance - results.initial_balance:,.2f}")
        print(f"  Return:           {((results.final_balance / results.initial_balance - 1) * 100):.2f}%")
        print(f"\nTrade Statistics:")
        print(f"  Total Trades:     {results.total_trades}")
        print(f"  Winning Trades:   {results.winning_trades}")
        print(f"  Losing Trades:    {results.losing_trades}")
        print(f"  Win Rate:         {results.win_rate:.1f}%")
        print(f"\nProfit/Loss:")
        print(f"  Total Profit:     ${results.total_profit_usd:,.2f}")
        print(f"  Total Loss:       ${results.total_loss_usd:,.2f}")
        print(f"  Avg Win:          ${results.avg_win_usd:.2f}")
        print(f"  Avg Loss:         ${results.avg_loss_usd:.2f}")
        print(f"  Profit Factor:    {results.profit_factor:.2f}")
        print(f"  Total Pips:       {results.total_pips:.1f}")
        print(f"\nRisk Metrics:")
        print(f"  Max Drawdown:     ${results.max_drawdown_usd:,.2f} ({results.max_drawdown_pct:.2f}%)")
        print(f"{'='*80}\n")

    @staticmethod
    def compare_results(all_results: List[BacktestResults]):
        """Compare results across multiple symbols"""
        if not all_results:
            return

        print(f"\n{'='*100}")
        print(f"MULTI-SYMBOL COMPARISON")
        print(f"{'='*100}")
        print(f"{'Symbol':<10} {'Trades':<8} {'Win%':<8} {'Net Profit':<15} {'Return%':<10} {'Max DD%':<10} {'P.Factor':<10}")
        print(f"{'-'*100}")

        for result in sorted(all_results, key=lambda x: x.final_balance - x.initial_balance, reverse=True):
            net_profit = result.final_balance - result.initial_balance
            return_pct = (result.final_balance / result.initial_balance - 1) * 100

            print(f"{result.symbol:<10} "
                  f"{result.total_trades:<8} "
                  f"{result.win_rate:<7.1f}% "
                  f"${net_profit:<14,.2f} "
                  f"{return_pct:<9.2f}% "
                  f"{result.max_drawdown_pct:<9.2f}% "
                  f"{result.profit_factor:<10.2f}")

        print(f"{'-'*100}")

        # Best pair
        best = max(all_results, key=lambda x: x.final_balance - x.initial_balance)
        print(f"\n[BEST PAIR] {best.symbol} - Net Profit: ${best.final_balance - best.initial_balance:,.2f}")
        print(f"{'='*100}\n")

    @staticmethod
    def export_to_csv(results: BacktestResults, filename: str):
        """Export backtest results to CSV"""
        trades_data = []

        for position in [p for p in results.positions if not p.is_open]:
            trades_data.append({
                'entry_time': position.entry_time,
                'exit_time': position.exit_time,
                'direction': position.position_type,
                'entry_price': position.entry_price,
                'exit_price': position.exit_price,
                'lot_size': position.lot_size,
                'level_type': position.level_type,
                'level_number': position.level_number,
                'profit_pips': position.profit_pips,
                'profit_usd': position.profit_usd,
            })

        df = pd.DataFrame(trades_data)
        df.to_csv(filename, index=False)
        print(f"[INFO] Exported {len(trades_data)} trades to {filename}")

    @staticmethod
    def export_summary_json(all_results: List[BacktestResults], filename: str):
        """Export summary comparison to JSON"""
        summary = []

        for result in all_results:
            summary.append({
                'symbol': result.symbol,
                'total_trades': result.total_trades,
                'win_rate': result.win_rate,
                'net_profit': result.final_balance - result.initial_balance,
                'return_pct': (result.final_balance / result.initial_balance - 1) * 100,
                'max_drawdown_pct': result.max_drawdown_pct,
                'profit_factor': result.profit_factor,
                'total_pips': result.total_pips,
            })

        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"[INFO] Exported summary to {filename}")


def main():
    """Main backtest execution"""
    parser = argparse.ArgumentParser(description='Backtest Ganymede Trade City strategy')
    parser.add_argument('--symbols', type=str, default='EURUSD',
                       help='Comma-separated list of symbols (e.g., EURUSD,GBPUSD,USDJPY)')
    parser.add_argument('--timeframe', type=str, default='M15',
                       choices=['M15', 'M30', 'H1', 'H4', 'D1'],
                       help='Timeframe for backtest')
    parser.add_argument('--days', type=int, default=90,
                       help='Number of days to backtest')
    parser.add_argument('--balance', type=float, default=10000.0,
                       help='Initial balance')
    parser.add_argument('--export', action='store_true',
                       help='Export results to CSV')

    args = parser.parse_args()

    # Parse symbols
    symbols = [s.strip() for s in args.symbols.split(',')]

    print(f"\n{'='*80}")
    print(f"GANYMEDE TRADE CITY - BACKTEST MODULE")
    print(f"{'='*80}")
    print(f"Symbols:     {', '.join(symbols)}")
    print(f"Timeframe:   {args.timeframe}")
    print(f"Period:      {args.days} days")
    print(f"Balance:     ${args.balance:,.2f}")
    print(f"{'='*80}\n")

    # Connect to MT5
    data_loader = BacktestDataLoader()
    if not data_loader.connect_mt5():
        return

    # Run backtests for each symbol
    all_results = []

    for symbol in symbols:
        # Load historical data
        historical_data = data_loader.load_historical_data(symbol, args.timeframe, args.days)

        if historical_data.empty:
            print(f"[ERROR] Skipping {symbol} - no data available")
            continue

        # Run backtest
        engine = BacktestEngine(symbol, args.balance)
        results = engine.run_backtest(historical_data)

        if results:
            all_results.append(results)

            # Print individual results
            BacktestReporter.print_summary(results)

            # Export to CSV if requested
            if args.export:
                filename = f"backtest_{symbol}_{args.timeframe}_{args.days}days.csv"
                BacktestReporter.export_to_csv(results, filename)

    # Disconnect from MT5
    data_loader.disconnect_mt5()

    # Compare results if multiple symbols
    if len(all_results) > 1:
        BacktestReporter.compare_results(all_results)

        # Export comparison summary
        if args.export:
            BacktestReporter.export_summary_json(all_results, f"backtest_summary_{args.timeframe}_{args.days}days.json")

    print("[INFO] Backtest completed!")


if __name__ == "__main__":
    main()
