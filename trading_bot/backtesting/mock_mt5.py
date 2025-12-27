"""
Mock MT5 Manager for Backtesting
Simulates MT5 broker behavior using historical data
"""

import pandas as pd
import MetaTrader5 as mt5
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import numpy as np


class MockMT5Manager:
    """
    Mock MT5 Manager for backtesting
    Simulates broker behavior without live connection
    """

    def __init__(self, initial_balance: float = 10000.0, spread_pips: float = 1.0):
        """
        Initialize mock MT5 manager

        Args:
            initial_balance: Starting account balance
            spread_pips: Spread in pips for all trades
        """
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        self.spread_pips = spread_pips

        # Trade tracking
        self.positions = {}  # ticket -> position dict
        self.closed_trades = []
        self.next_ticket = 1000

        # Historical data cache
        self.historical_data = {}  # (symbol, timeframe) -> DataFrame
        self.current_time = None
        self.current_prices = {}  # symbol -> current price

        # Statistics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0.0
        self.total_loss = 0.0

        # Connection state
        self.connected = False

    def load_historical_data(self, symbol: str, timeframe: str, data: pd.DataFrame):
        """
        Load historical data for backtesting

        Args:
            symbol: Trading symbol
            timeframe: Timeframe (H1, D1, W1)
            data: Historical OHLCV DataFrame
        """
        key = (symbol, timeframe)
        # Ensure data is sorted by time
        data = data.sort_values('time').reset_index(drop=True)
        self.historical_data[key] = data

    def set_current_time(self, timestamp: datetime):
        """
        Set current backtesting time

        Args:
            timestamp: Current simulation time
        """
        self.current_time = timestamp

        # Update current prices from historical data
        for (symbol, timeframe), data in self.historical_data.items():
            if timeframe == 'H1':  # Use H1 for current price
                # Find closest bar <= current_time
                mask = data['time'] <= timestamp
                if mask.any():
                    latest_bar = data[mask].iloc[-1]
                    self.current_prices[symbol] = latest_bar['close']

    def connect(self, login: int, password: str, server: str) -> bool:
        """Mock connect (always succeeds in backtest)"""
        self.connected = True
        return True

    def disconnect(self) -> None:
        """Mock disconnect"""
        self.connected = False

    def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        bars: int
    ) -> Optional[pd.DataFrame]:
        """
        Get historical data up to current_time

        Args:
            symbol: Trading symbol
            timeframe: Timeframe (H1, D1, W1)
            bars: Number of bars to return

        Returns:
            DataFrame with OHLCV data or None
        """
        key = (symbol, timeframe)
        if key not in self.historical_data:
            return None

        data = self.historical_data[key]

        # Filter data up to current_time
        mask = data['time'] <= self.current_time
        available_data = data[mask]

        if len(available_data) == 0:
            return None

        # Return last 'bars' rows
        return available_data.tail(bars).copy()

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        Get symbol information

        Args:
            symbol: Trading symbol

        Returns:
            Dict with symbol info
        """
        # Standard forex symbol info
        pip_value = 0.0001 if 'JPY' not in symbol else 0.01

        return {
            'symbol': symbol,
            'digits': 5 if pip_value == 0.0001 else 3,
            'point': pip_value,
            'volume_min': 0.01,
            'volume_max': 100.0,
            'volume_step': 0.01,
            'spread': int(self.spread_pips / pip_value),
            'trade_contract_size': 100000
        }

    def get_account_info(self) -> Optional[Dict]:
        """
        Get account information

        Returns:
            Dict with account info
        """
        # Calculate equity (balance + floating P&L)
        floating_pl = sum(pos['profit'] for pos in self.positions.values())
        self.equity = self.balance + floating_pl

        return {
            'balance': self.balance,
            'equity': self.equity,
            'profit': floating_pl,
            'margin': 0.0,  # Simplified for backtest
            'margin_free': self.equity,
            'margin_level': 0.0
        }

    def get_positions(self) -> List[Dict]:
        """
        Get all open positions

        Returns:
            List of position dicts
        """
        return list(self.positions.values())

    def place_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = ""
    ) -> Optional[int]:
        """
        Place a new order (simulated)

        Args:
            symbol: Trading symbol
            order_type: 'buy' or 'sell'
            volume: Lot size
            sl: Stop loss price (optional)
            tp: Take profit price (optional)
            comment: Order comment

        Returns:
            Ticket number or None if failed
        """
        if symbol not in self.current_prices:
            return None

        # Get entry price (with spread)
        base_price = self.current_prices[symbol]
        symbol_info = self.get_symbol_info(symbol)
        spread = self.spread_pips * symbol_info['point']

        if order_type.lower() == 'buy':
            entry_price = base_price + spread  # Buy at ask
            position_type = 'buy'
        else:
            entry_price = base_price  # Sell at bid
            position_type = 'sell'

        # Create position
        ticket = self.next_ticket
        self.next_ticket += 1

        position = {
            'ticket': ticket,
            'symbol': symbol,
            'type': position_type,
            'volume': volume,
            'price_open': entry_price,
            'price_current': base_price,
            'sl': sl,
            'tp': tp,
            'profit': 0.0,
            'swap': 0.0,
            'commission': 0.0,
            'comment': comment,
            'time': self.current_time
        }

        self.positions[ticket] = position
        self.total_trades += 1

        return ticket

    def close_position(self, ticket: int) -> bool:
        """
        Close a position (simulated)

        Args:
            ticket: Position ticket

        Returns:
            True if closed, False if failed
        """
        if ticket not in self.positions:
            return False

        position = self.positions[ticket]
        symbol = position['symbol']

        # Update position with current price and profit
        self._update_position_profit(position)

        # Close the trade
        profit = position['profit']
        self.balance += profit
        self.total_profit += profit if profit > 0 else 0
        self.total_loss += abs(profit) if profit < 0 else 0

        if profit > 0:
            self.winning_trades += 1
        elif profit < 0:
            self.losing_trades += 1

        # Store closed trade
        closed_trade = position.copy()
        closed_trade['time_close'] = self.current_time
        closed_trade['price_close'] = position['price_current']
        self.closed_trades.append(closed_trade)

        # Remove from open positions
        del self.positions[ticket]

        return True

    def close_partial_position(self, ticket: int, volume: float) -> bool:
        """
        Close partial volume of a position

        Args:
            ticket: Position ticket
            volume: Volume to close

        Returns:
            True if closed, False if failed
        """
        if ticket not in self.positions:
            return False

        position = self.positions[ticket]

        if volume >= position['volume']:
            # Close entire position
            return self.close_position(ticket)

        # Update position with current price
        self._update_position_profit(position)

        # Calculate partial profit
        volume_ratio = volume / position['volume']
        partial_profit = position['profit'] * volume_ratio

        # Update balance
        self.balance += partial_profit
        self.total_profit += partial_profit if partial_profit > 0 else 0
        self.total_loss += abs(partial_profit) if partial_profit < 0 else 0

        # Store partial close as a trade
        closed_trade = position.copy()
        closed_trade['volume'] = volume
        closed_trade['profit'] = partial_profit
        closed_trade['time_close'] = self.current_time
        closed_trade['price_close'] = position['price_current']
        closed_trade['comment'] = f"Partial close of {position['comment']}"
        self.closed_trades.append(closed_trade)

        # Reduce position volume
        position['volume'] -= volume
        position['profit'] *= (1 - volume_ratio)

        return True

    def _update_position_profit(self, position: Dict) -> None:
        """
        Update position's current price and profit

        Args:
            position: Position dict
        """
        symbol = position['symbol']
        if symbol not in self.current_prices:
            return

        current_price = self.current_prices[symbol]
        position['price_current'] = current_price

        # Calculate profit
        symbol_info = self.get_symbol_info(symbol)
        point = symbol_info['point']
        contract_size = symbol_info['trade_contract_size']

        if position['type'] == 'buy':
            price_diff = current_price - position['price_open']
        else:  # sell
            price_diff = position['price_open'] - current_price

        pips = price_diff / point
        position['profit'] = pips * point * position['volume'] * contract_size

    def update_all_positions(self):
        """Update all open positions with current prices and P&L"""
        for position in self.positions.values():
            self._update_position_profit(position)

            # Check TP/SL
            symbol = position['symbol']
            current_price = self.current_prices.get(symbol)
            if current_price is None:
                continue

            # Check take profit
            if position['tp'] is not None:
                if position['type'] == 'buy' and current_price >= position['tp']:
                    self.close_position(position['ticket'])
                elif position['type'] == 'sell' and current_price <= position['tp']:
                    self.close_position(position['ticket'])

            # Check stop loss
            if position['sl'] is not None:
                if position['type'] == 'buy' and current_price <= position['sl']:
                    self.close_position(position['ticket'])
                elif position['type'] == 'sell' and current_price >= position['sl']:
                    self.close_position(position['ticket'])

    def get_trade_history(self) -> List[Dict]:
        """
        Get all closed trades

        Returns:
            List of closed trade dicts
        """
        return self.closed_trades.copy()

    def get_statistics(self) -> Dict:
        """
        Get trading statistics

        Returns:
            Dict with performance metrics
        """
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        profit_factor = (self.total_profit / abs(self.total_loss)) if self.total_loss != 0 else 0

        return {
            'initial_balance': self.initial_balance,
            'final_balance': self.balance,
            'final_equity': self.equity,
            'net_profit': self.balance - self.initial_balance,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'total_profit': self.total_profit,
            'total_loss': self.total_loss,
            'profit_factor': profit_factor
        }
