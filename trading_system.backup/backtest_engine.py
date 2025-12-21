#!/usr/bin/env python3
"""
Backtesting Engine for Ganymede Trade City Strategy
Simulates full strategy (grid, hedge, recovery, confluence) on historical data
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

import trading_config as config
from confluence_analyzer import ConfluenceAnalyzer
from position_managers import GridManager, HedgeManager, RecoveryManager
from risk_manager import RiskManager


@dataclass
class BacktestPosition:
    """Simulated position for backtesting"""
    entry_time: datetime
    entry_price: float
    type: str  # 'buy' or 'sell'
    lot_size: float
    level_type: str  # 'initial', 'grid', 'hedge', 'recovery'
    level_number: int
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    profit_pips: Optional[float] = None
    profit_usd: Optional[float] = None
    is_open: bool = True

    def close(self, exit_price: float, exit_time: datetime):
        """Close the position"""
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.is_open = False

        # Calculate profit in pips
        if self.type == 'buy':
            self.profit_pips = (exit_price - self.entry_price) / config.POINT_VALUE
        else:
            self.profit_pips = (self.entry_price - exit_price) / config.POINT_VALUE

        # Calculate profit in USD (rough approximation)
        self.profit_usd = self.profit_pips * self.lot_size * 10

    def get_pips_profit(self, current_price: float) -> float:
        """Calculate current profit in pips"""
        if self.type == 'buy':
            return (current_price - self.entry_price) / config.POINT_VALUE
        else:
            return (self.entry_price - current_price) / config.POINT_VALUE


@dataclass
class BacktestResults:
    """Results from backtesting a symbol"""
    symbol: str
    start_date: datetime
    end_date: datetime
    initial_balance: float
    final_balance: float
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit_usd: float = 0.0
    total_loss_usd: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_usd: float = 0.0
    win_rate: float = 0.0
    avg_win_usd: float = 0.0
    avg_loss_usd: float = 0.0
    profit_factor: float = 0.0
    total_pips: float = 0.0
    positions: List[BacktestPosition] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)

    def calculate_metrics(self):
        """Calculate all performance metrics"""
        closed_positions = [p for p in self.positions if not p.is_open]

        if not closed_positions:
            return

        self.total_trades = len(closed_positions)

        # Win/Loss counts
        winning_positions = [p for p in closed_positions if p.profit_usd > 0]
        losing_positions = [p for p in closed_positions if p.profit_usd <= 0]

        self.winning_trades = len(winning_positions)
        self.losing_trades = len(losing_positions)

        # Profit/Loss totals
        self.total_profit_usd = sum(p.profit_usd for p in winning_positions)
        self.total_loss_usd = abs(sum(p.profit_usd for p in losing_positions))

        # Win rate
        self.win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0.0

        # Average win/loss
        self.avg_win_usd = self.total_profit_usd / self.winning_trades if self.winning_trades > 0 else 0.0
        self.avg_loss_usd = self.total_loss_usd / self.losing_trades if self.losing_trades > 0 else 0.0

        # Profit factor
        self.profit_factor = self.total_profit_usd / self.total_loss_usd if self.total_loss_usd > 0 else 0.0

        # Total pips
        self.total_pips = sum(p.profit_pips for p in closed_positions)

        # Final balance
        net_profit = self.total_profit_usd - self.total_loss_usd
        self.final_balance = self.initial_balance + net_profit

        # Max drawdown
        if self.equity_curve:
            peak = self.initial_balance
            max_dd = 0

            for equity in self.equity_curve:
                if equity > peak:
                    peak = equity
                dd = peak - equity
                if dd > max_dd:
                    max_dd = dd

            self.max_drawdown_usd = max_dd
            self.max_drawdown_pct = (max_dd / peak * 100) if peak > 0 else 0.0


class BacktestEngine:
    """Simulates trading strategy on historical data"""

    def __init__(self, symbol: str, initial_balance: float = 10000.0):
        self.symbol = symbol
        self.initial_balance = initial_balance
        self.balance = initial_balance

        # Initialize strategy components
        self.confluence_analyzer = ConfluenceAnalyzer()
        self.grid_manager = GridManager()
        self.hedge_manager = HedgeManager()
        self.recovery_manager = RecoveryManager()
        self.risk_manager = RiskManager(initial_balance)

        # Positions tracking
        self.positions: List[BacktestPosition] = []
        self.equity_curve: List[float] = []

        # Statistics
        self.trades_opened = 0
        self.trades_closed = 0

    def run_backtest(self, historical_data: pd.DataFrame,
                     start_date: Optional[datetime] = None,
                     end_date: Optional[datetime] = None) -> BacktestResults:
        """
        Run backtest on historical data

        Args:
            historical_data: DataFrame with OHLCV data and VWAP
            start_date: Start date for backtest (None = use all data)
            end_date: End date for backtest (None = use all data)

        Returns:
            BacktestResults object with performance metrics
        """
        # Filter data by date range
        if start_date:
            historical_data = historical_data[historical_data.index >= start_date]
        if end_date:
            historical_data = historical_data[historical_data.index <= end_date]

        if historical_data.empty:
            print(f"[ERROR] No data available for {self.symbol}")
            return None

        print(f"\n[BACKTEST] Starting backtest for {self.symbol}")
        print(f"  Period: {historical_data.index[0]} to {historical_data.index[-1]}")
        print(f"  Bars: {len(historical_data)}")

        # Calculate VWAP if not present
        if 'VWAP' not in historical_data.columns:
            historical_data['VWAP'] = (historical_data['close'] * historical_data['tick_volume']).cumsum() / \
                                      historical_data['tick_volume'].cumsum()

        # Iterate through each bar
        for i in range(config.VP_LOOKBACK_BARS, len(historical_data)):
            current_bar = historical_data.iloc[i]
            current_time = current_bar.name
            current_price = current_bar['close']

            # Get lookback data for analysis
            lookback_data = historical_data.iloc[:i+1]

            # Update previous day levels periodically
            if i % 100 == 0:  # Update every 100 bars
                self.confluence_analyzer.calculate_previous_day_levels(lookback_data)

            # Manage existing positions
            self._manage_positions(current_price, current_time)

            # Check for new entry signals (only if no open positions)
            open_positions = [p for p in self.positions if p.is_open]

            if not open_positions:
                # Check risk controls
                can_trade, reason = self.risk_manager.can_trade(self.positions, self.symbol, current_time)

                if can_trade:
                    signal = self._check_entry_signal(current_price, lookback_data)

                    if signal:
                        # Execute initial entry
                        self._open_position(
                            current_time,
                            current_price,
                            signal['direction'],
                            config.GRID_BASE_LOT_SIZE,
                            'initial',
                            0
                        )

            # Update equity curve
            self._update_equity(current_price)

        # Close any remaining open positions at the end
        for position in [p for p in self.positions if p.is_open]:
            final_price = historical_data.iloc[-1]['close']
            position.close(final_price, historical_data.index[-1])
            self.trades_closed += 1
            self.risk_manager.record_trade_result(position.profit_usd)

        # Create results
        results = BacktestResults(
            symbol=self.symbol,
            start_date=historical_data.index[0],
            end_date=historical_data.index[-1],
            initial_balance=self.initial_balance,
            final_balance=self.balance,
            positions=self.positions,
            equity_curve=self.equity_curve
        )

        results.calculate_metrics()

        return results

    def _check_entry_signal(self, current_price: float, current_data: pd.DataFrame) -> Optional[Dict]:
        """Check for entry signals using confluence analysis"""
        signal = self.confluence_analyzer.analyze_confluence(current_price, current_data)
        return signal if signal.get('should_trade') else None

    def _open_position(self, time: datetime, price: float, direction: str,
                      lot_size: float, level_type: str, level_number: int) -> BacktestPosition:
        """Open a simulated position"""
        position = BacktestPosition(
            entry_time=time,
            entry_price=price,
            type=direction,
            lot_size=lot_size,
            level_type=level_type,
            level_number=level_number
        )

        self.positions.append(position)
        self.trades_opened += 1

        return position

    def _close_position(self, position: BacktestPosition, price: float, time: datetime):
        """Close a position"""
        position.close(price, time)
        self.trades_closed += 1

        # Update balance
        self.balance += position.profit_usd

        # Update risk manager
        self.risk_manager.record_trade_result(position.profit_usd)

    def _manage_positions(self, current_price: float, current_time: datetime):
        """Manage existing positions (grid, hedge, recovery)"""
        open_positions = [p for p in self.positions if p.is_open]

        if not open_positions:
            return

        # Group positions by direction
        buy_positions = [p for p in open_positions if p.type == 'buy']
        sell_positions = [p for p in open_positions if p.type == 'sell']

        # Manage buy positions
        if buy_positions:
            self._manage_direction_positions(buy_positions, current_price, current_time, 'buy')

        # Manage sell positions
        if sell_positions:
            self._manage_direction_positions(sell_positions, current_price, current_time, 'sell')

    def _manage_direction_positions(self, positions: List[BacktestPosition],
                                   current_price: float, current_time: datetime, direction: str):
        """Manage positions for a specific direction"""
        # Check if we should add grid level
        if self.grid_manager.should_open_grid_level(positions, current_price, direction):
            grid_level = len([p for p in positions if p.level_type in ['initial', 'grid']])
            lot_size = self.grid_manager.get_grid_lot_size(grid_level)

            self._open_position(current_time, current_price, direction, lot_size, 'grid', grid_level)

        # Check if we should open hedge
        should_hedge, hedge_direction, hedge_lot_size = self.hedge_manager.should_open_hedge(
            positions, current_price
        )

        if should_hedge:
            self._open_position(current_time, current_price, hedge_direction, hedge_lot_size, 'hedge', 0)

        # Check if we should close hedge
        if self.hedge_manager.should_close_hedge(positions, current_price):
            hedge_positions = [p for p in positions if p.level_type == 'hedge']
            for hedge_pos in hedge_positions:
                self._close_position(hedge_pos, current_price, current_time)

        # Check if we should start/continue recovery
        should_recover, recovery_lot_size = self.recovery_manager.should_open_recovery_level(
            positions, current_price, direction
        )

        if should_recover:
            recovery_level = len([p for p in positions if p.level_type == 'recovery']) + 1
            self._open_position(current_time, current_price, direction, recovery_lot_size, 'recovery', recovery_level)

        # Check if we should close all positions (breakeven or profit)
        self._check_exit_conditions(positions, current_price, current_time, direction)

    def _check_exit_conditions(self, positions: List[BacktestPosition],
                               current_price: float, current_time: datetime, direction: str):
        """Check if we should exit positions"""
        # Calculate total P&L
        total_pnl_pips = sum(p.get_pips_profit(current_price) * p.lot_size for p in positions)

        # Close all if profitable (breakeven or better)
        if total_pnl_pips > 0:
            for position in positions:
                self._close_position(position, current_price, current_time)

    def _update_equity(self, current_price: float):
        """Update equity curve"""
        open_positions = [p for p in self.positions if p.is_open]
        floating_pnl = sum(p.get_pips_profit(current_price) * p.lot_size * 10 for p in open_positions)

        current_equity = self.balance + floating_pnl
        self.equity_curve.append(current_equity)
