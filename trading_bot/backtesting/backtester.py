"""
Backtesting Engine
Replays historical data through production strategy code
"""

import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

from .mock_mt5 import MockMT5Manager
from ..strategies.confluence_strategy import ConfluenceStrategy
from ..utils.logger import logger


class Backtester:
    """
    Main backtesting engine
    Replays historical data through production strategy
    """

    def __init__(
        self,
        initial_balance: float = 10000.0,
        spread_pips: float = 1.0,
        symbols: List[str] = None
    ):
        """
        Initialize backtester

        Args:
            initial_balance: Starting account balance
            spread_pips: Spread in pips for all trades
            symbols: List of symbols to backtest
        """
        self.initial_balance = initial_balance
        self.spread_pips = spread_pips
        self.symbols = symbols or ['EURUSD', 'GBPUSD']

        # Initialize mock MT5
        self.mock_mt5 = MockMT5Manager(initial_balance, spread_pips)
        self.mock_mt5.connect(0, "", "")  # Mock connection

        # Initialize production strategy with mock MT5
        self.strategy = ConfluenceStrategy(self.mock_mt5, test_mode=True)

        # Backtest state
        self.start_date = None
        self.end_date = None
        self.current_time = None

        # Event log
        self.events = []

    def load_data_from_mt5(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Load historical data from MT5

        Args:
            symbol: Trading symbol
            timeframe: Timeframe (H1, D1, W1)
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with OHLCV data
        """
        import MetaTrader5 as mt5

        # Map timeframe string to MT5 constant
        timeframe_map = {
            'H1': mt5.TIMEFRAME_H1,
            'D1': mt5.TIMEFRAME_D1,
            'W1': mt5.TIMEFRAME_W1
        }

        tf = timeframe_map.get(timeframe)
        if tf is None:
            raise ValueError(f"Unknown timeframe: {timeframe}")

        # Fetch data from MT5
        rates = mt5.copy_rates_range(symbol, tf, start_date, end_date)

        if rates is None or len(rates) == 0:
            logger.error(f"Failed to fetch data for {symbol} {timeframe}")
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        return df

    def load_data_from_csv(
        self,
        symbol: str,
        timeframe: str,
        filepath: str
    ) -> pd.DataFrame:
        """
        Load historical data from CSV file

        Args:
            symbol: Trading symbol
            timeframe: Timeframe (H1, D1, W1)
            filepath: Path to CSV file

        Returns:
            DataFrame with OHLCV data
        """
        df = pd.read_csv(filepath)

        # Ensure required columns
        required_cols = ['time', 'open', 'high', 'low', 'close', 'tick_volume']
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"CSV missing required columns: {required_cols}")

        # Parse time column
        df['time'] = pd.to_datetime(df['time'])

        return df

    def load_all_data(
        self,
        data_source: str,
        start_date: datetime,
        end_date: datetime,
        data_paths: Optional[Dict[str, Dict[str, str]]] = None
    ) -> None:
        """
        Load all required data for backtesting

        Args:
            data_source: 'mt5' or 'csv'
            start_date: Start date for backtest
            end_date: End date for backtest
            data_paths: Dict mapping (symbol, timeframe) -> filepath (for CSV only)
        """
        self.start_date = start_date
        self.end_date = end_date

        logger.info(f"Loading data from {start_date} to {end_date}")

        # Add lookback buffer for higher timeframes to have historical context
        lookback_days = {
            'H1': 10,   # 10 days extra for H1 (ensures 100+ bars minimum)
            'D1': 60,   # 60 days extra for D1 (for indicators)
            'W1': 180   # 180 days extra for W1 (for weekly indicators)
        }

        for symbol in self.symbols:
            for timeframe in ['H1', 'D1', 'W1']:
                # Calculate buffered start date
                buffer_days = lookback_days.get(timeframe, 0)
                buffered_start = start_date - timedelta(days=buffer_days)

                logger.info(f"Loading {symbol} {timeframe} (with {buffer_days}-day lookback)...")

                if data_source == 'mt5':
                    data = self.load_data_from_mt5(symbol, timeframe, buffered_start, end_date)
                elif data_source == 'csv':
                    if data_paths is None:
                        raise ValueError("data_paths required for CSV source")

                    key = (symbol, timeframe)
                    if key not in data_paths:
                        raise ValueError(f"No CSV path for {symbol} {timeframe}")

                    # Load CSV data (will be filtered by date range after loading)
                    data = self.load_data_from_csv(symbol, timeframe, data_paths[key])

                    # Filter to buffered date range
                    if len(data) > 0 and 'time' in data.columns:
                        mask = (data['time'] >= buffered_start) & (data['time'] <= end_date)
                        data = data[mask].copy()
                else:
                    raise ValueError(f"Unknown data source: {data_source}")

                if len(data) == 0:
                    logger.warning(f"No data loaded for {symbol} {timeframe}")
                    continue

                # Load into mock MT5
                self.mock_mt5.load_historical_data(symbol, timeframe, data)

                # Log data range for debugging
                if len(data) > 0:
                    first_time = data['time'].iloc[0]
                    last_time = data['time'].iloc[-1]
                    logger.info(
                        f"Loaded {len(data)} bars for {symbol} {timeframe} "
                        f"({first_time.strftime('%Y-%m-%d')} to {last_time.strftime('%Y-%m-%d')})"
                    )
                else:
                    logger.warning(f"Loaded 0 bars for {symbol} {timeframe}")

    def run(self, check_interval_hours: int = 1) -> None:
        """
        Run backtest by replaying historical data

        Args:
            check_interval_hours: Hours between strategy checks (default 1)
        """
        if self.start_date is None or self.end_date is None:
            raise ValueError("Must call load_all_data() before run()")

        logger.info("=" * 80)
        logger.info(f"Starting backtest: {self.start_date} to {self.end_date}")
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Initial Balance: ${self.initial_balance:,.2f}")
        logger.info("=" * 80)

        # Start from beginning
        self.current_time = self.start_date
        interval = timedelta(hours=check_interval_hours)

        iteration = 0
        while self.current_time <= self.end_date:
            iteration += 1

            # Update mock MT5 time
            self.mock_mt5.set_current_time(self.current_time)

            # Update all positions (check TP/SL, calculate P&L)
            self.mock_mt5.update_all_positions()

            # Run strategy loop
            try:
                self.strategy.run_once(self.symbols)
            except Exception as e:
                logger.error(f"Strategy error at {self.current_time}: {e}")
                self._log_event('error', f"Strategy error: {e}")

            # Log progress every 24 hours
            if iteration % 24 == 0:
                account_info = self.mock_mt5.get_account_info()
                positions_count = len(self.mock_mt5.get_positions())

                logger.info(
                    f"[{self.current_time}] "
                    f"Balance: ${account_info['balance']:,.2f} | "
                    f"Equity: ${account_info['equity']:,.2f} | "
                    f"Open Positions: {positions_count}"
                )

            # Advance time
            self.current_time += interval

        # Close all remaining positions
        self._close_all_positions()

        logger.info("=" * 80)
        logger.info("Backtest completed!")
        logger.info("=" * 80)

    def _close_all_positions(self) -> None:
        """Close all remaining positions at end of backtest"""
        positions = self.mock_mt5.get_positions()

        if len(positions) > 0:
            logger.info(f"Closing {len(positions)} remaining positions...")

            for pos in positions:
                self.mock_mt5.close_position(pos['ticket'])
                logger.info(f"Closed {pos['symbol']} position (ticket {pos['ticket']})")

    def _log_event(self, event_type: str, message: str) -> None:
        """
        Log backtest event

        Args:
            event_type: Type of event
            message: Event message
        """
        self.events.append({
            'time': self.current_time,
            'type': event_type,
            'message': message
        })

    def get_results(self) -> Dict:
        """
        Get backtest results

        Returns:
            Dict with statistics and trade history
        """
        stats = self.mock_mt5.get_statistics()
        trades = self.mock_mt5.get_trade_history()

        # Calculate additional metrics
        if len(trades) > 0:
            trades_df = pd.DataFrame(trades)

            # Profit by symbol
            profit_by_symbol = trades_df.groupby('symbol')['profit'].sum().to_dict()

            # Profit by strategy (from comment)
            trades_df['strategy'] = trades_df['comment'].apply(
                lambda x: 'Breakout' if 'Breakout' in x else 'Mean Reversion' if 'Confluence' in x else 'Other'
            )
            profit_by_strategy = trades_df.groupby('strategy')['profit'].sum().to_dict()

            # Average trade duration
            trades_df['duration'] = (trades_df['time_close'] - trades_df['time']).dt.total_seconds() / 3600
            avg_duration = trades_df['duration'].mean()

            # Max drawdown calculation
            trades_df = trades_df.sort_values('time_close')
            trades_df['cumulative_profit'] = trades_df['profit'].cumsum()
            trades_df['cumulative_balance'] = self.initial_balance + trades_df['cumulative_profit']
            trades_df['peak'] = trades_df['cumulative_balance'].cumsum().max()
            trades_df['drawdown'] = trades_df['peak'] - trades_df['cumulative_balance']
            max_drawdown = trades_df['drawdown'].max()

        else:
            profit_by_symbol = {}
            profit_by_strategy = {}
            avg_duration = 0
            max_drawdown = 0

        return {
            'statistics': stats,
            'trades': trades,
            'profit_by_symbol': profit_by_symbol,
            'profit_by_strategy': profit_by_strategy,
            'avg_trade_duration_hours': avg_duration,
            'max_drawdown': max_drawdown,
            'events': self.events
        }

    def print_summary(self) -> None:
        """Print backtest summary to console"""
        results = self.get_results()
        stats = results['statistics']

        print("\n" + "=" * 80)
        print("BACKTEST SUMMARY")
        print("=" * 80)

        print(f"\nPerformance:")
        print(f"   Initial Balance:    ${stats['initial_balance']:>12,.2f}")
        print(f"   Final Balance:      ${stats['final_balance']:>12,.2f}")
        print(f"   Final Equity:       ${stats['final_equity']:>12,.2f}")
        print(f"   Net Profit:         ${stats['net_profit']:>12,.2f}")
        print(f"   Max Drawdown:       ${results['max_drawdown']:>12,.2f}")
        print(f"   Return:             {(stats['net_profit'] / stats['initial_balance'] * 100):>12.2f}%")

        print(f"\nTrading Activity:")
        print(f"   Total Trades:       {stats['total_trades']:>12}")
        print(f"   Winning Trades:     {stats['winning_trades']:>12}")
        print(f"   Losing Trades:      {stats['losing_trades']:>12}")
        print(f"   Win Rate:           {stats['win_rate']:>12.2f}%")

        print(f"\nProfit Metrics:")
        print(f"   Total Profit:       ${stats['total_profit']:>12,.2f}")
        print(f"   Total Loss:         ${stats['total_loss']:>12,.2f}")
        print(f"   Profit Factor:      {stats['profit_factor']:>12.2f}")
        print(f"   Avg Trade Duration: {results['avg_trade_duration_hours']:>12.1f} hours")

        print(f"\n📍 Profit by Symbol:")
        for symbol, profit in results['profit_by_symbol'].items():
            print(f"   {symbol:>10}:       ${profit:>12,.2f}")

        print(f"\nProfit by Strategy:")
        for strategy, profit in results['profit_by_strategy'].items():
            print(f"   {strategy:>15}:   ${profit:>12,.2f}")

        print("\n" + "=" * 80)
