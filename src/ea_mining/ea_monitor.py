"""
EA Monitor
Monitors an existing EA running on MT5 account and tracks all its trades
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import time

from ..mt5_connection import MT5ConnectionManager
from ..data import DataStorage


@dataclass
class EATrade:
    """Represents a trade made by the EA"""
    ticket: int
    symbol: str
    trade_type: str  # 'buy' or 'sell'

    # Entry
    entry_time: datetime
    entry_price: float
    volume: float

    # Exit (None if still open)
    exit_time: Optional[datetime]
    exit_price: Optional[float]

    # Levels
    stop_loss: Optional[float]
    take_profit: Optional[float]

    # Results
    profit: Optional[float]
    commission: Optional[float]
    swap: Optional[float]

    # Market conditions at entry
    market_conditions: Dict

    # EA identifiers
    magic_number: Optional[int]
    comment: Optional[str]

    @property
    def is_open(self) -> bool:
        """Check if trade is still open"""
        return self.exit_time is None

    @property
    def duration_hours(self) -> Optional[float]:
        """Trade duration in hours"""
        if self.exit_time is None:
            return None
        return (self.exit_time - self.entry_time).total_seconds() / 3600

    @property
    def pips(self) -> Optional[float]:
        """Profit in pips"""
        if self.exit_price is None:
            return None

        direction = 1 if self.trade_type == 'buy' else -1
        return (self.exit_price - self.entry_price) * direction * 10000  # Assumes 4-digit pairs


class EAMonitor:
    """Monitors an existing EA and collects its trading data"""

    def __init__(self, mt5_manager: MT5ConnectionManager, storage: DataStorage):
        """
        Initialize EA Monitor

        Args:
            mt5_manager: MT5 connection manager
            storage: Data storage instance
        """
        self.mt5 = mt5_manager
        self.storage = storage
        self.logger = logging.getLogger(__name__)

        # Track known trades
        self.known_trades: Dict[int, EATrade] = {}
        self.last_check: Optional[datetime] = None

    def start_monitoring(self, magic_number: Optional[int] = None,
                        symbol_filter: Optional[str] = None):
        """
        Start monitoring EA trades

        Args:
            magic_number: Filter by EA magic number (None = all trades)
            symbol_filter: Filter by symbol (None = all symbols)
        """
        self.logger.info("Starting EA monitoring...")

        # Load existing historical trades
        self.logger.info("Loading historical trades...")
        self._load_historical_trades(magic_number, symbol_filter)

        self.logger.info(f"Monitoring started. Tracking {len(self.known_trades)} existing trades")

    def update(self, current_data: Dict[str, pd.DataFrame]) -> List[EATrade]:
        """
        Update monitor with current market data

        Args:
            current_data: Dictionary of {symbol: DataFrame} with current market data

        Returns:
            List of new trades detected
        """
        new_trades = []

        # Check for new positions
        positions = self._get_open_positions()

        for position in positions:
            ticket = position['ticket']

            # New position detected
            if ticket not in self.known_trades:
                symbol = position['symbol']
                market_conditions = self._capture_market_conditions(
                    symbol,
                    current_data.get(symbol)
                )

                trade = EATrade(
                    ticket=ticket,
                    symbol=symbol,
                    trade_type='buy' if position['type'] == 0 else 'sell',
                    entry_time=position['time'],
                    entry_price=position['price_open'],
                    volume=position['volume'],
                    exit_time=None,
                    exit_price=None,
                    stop_loss=position.get('sl'),
                    take_profit=position.get('tp'),
                    profit=None,
                    commission=None,
                    swap=None,
                    market_conditions=market_conditions,
                    magic_number=position.get('magic'),
                    comment=position.get('comment', '')
                )

                self.known_trades[ticket] = trade
                new_trades.append(trade)

                self.logger.info(f"New EA trade detected: {ticket} {trade.trade_type.upper()} "
                               f"{trade.symbol} @ {trade.entry_price}")

        # Check for closed positions
        self._update_closed_trades()

        self.last_check = datetime.now()

        return new_trades

    def _get_open_positions(self) -> List[Dict]:
        """Get all open positions from MT5"""
        if not self.mt5.connected:
            return []

        try:
            import MetaTrader5 as mt5
            positions = mt5.positions_get()

            if positions is None:
                return []

            return [pos._asdict() for pos in positions]

        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return []

    def _update_closed_trades(self):
        """Check for trades that have been closed"""
        # Get recent deals (last 24 hours)
        end_time = datetime.now()
        start_time = self.last_check if self.last_check else end_time - timedelta(days=1)

        deals_df = self.mt5.get_historical_deals(start_time, end_time)

        if deals_df is None or deals_df.empty:
            return

        # Group deals by position_id to find closed positions
        for position_id in deals_df['position_id'].unique():
            if position_id == 0:
                continue

            position_deals = deals_df[deals_df['position_id'] == position_id]

            # Find exit deal (entry = 1 means exit)
            exit_deals = position_deals[position_deals['entry'] == 1]

            if not exit_deals.empty and position_id in self.known_trades:
                exit_deal = exit_deals.iloc[-1]

                trade = self.known_trades[position_id]
                trade.exit_time = exit_deal['time']
                trade.exit_price = exit_deal['price']
                trade.profit = position_deals['profit'].sum()
                trade.commission = position_deals['commission'].sum()
                trade.swap = position_deals['swap'].sum()

                self.logger.info(f"Trade closed: {position_id} {trade.symbol} "
                               f"Profit: ${trade.profit:.2f} ({trade.pips:.1f} pips)")

                # Store closed trade
                self._store_ea_trade(trade)

    def _load_historical_trades(self, magic_number: Optional[int], symbol_filter: Optional[str]):
        """Load historical trades from MT5 history"""
        # Get last 90 days of trades
        end_time = datetime.now()
        start_time = end_time - timedelta(days=90)

        # Get historical deals (executed trades)
        deals_df = self.mt5.get_historical_deals(start_time, end_time)

        if deals_df is None or deals_df.empty:
            self.logger.warning("No historical deals found")

            # Try with longer history (1 year)
            start_time = end_time - timedelta(days=365)
            deals_df = self.mt5.get_historical_deals(start_time, end_time)

            if deals_df is None or deals_df.empty:
                self.logger.warning("No historical deals found in past year")
                return

        self.logger.info(f"Loaded {len(deals_df)} historical deals")

        # Filter by magic number if specified
        if magic_number is not None:
            deals_df = deals_df[deals_df['magic'] == magic_number]
            self.logger.info(f"Filtered to {len(deals_df)} deals with magic number {magic_number}")

        # Filter by symbol if specified
        if symbol_filter:
            deals_df = deals_df[deals_df['symbol'] == symbol_filter]
            self.logger.info(f"Filtered to {len(deals_df)} deals for symbol {symbol_filter}")

        if deals_df.empty:
            self.logger.warning("No deals match the specified filters")
            return

        # Get historical orders (optional, for additional context)
        orders_df = self.mt5.get_historical_orders(start_time, end_time)
        if orders_df is not None and not orders_df.empty:
            self.logger.info(f"Loaded {len(orders_df)} historical orders")
        else:
            orders_df = pd.DataFrame()

        # Process historical trades
        self._process_historical_trades(orders_df, deals_df)

    def _process_historical_trades(self, orders_df: pd.DataFrame, deals_df: pd.DataFrame):
        """Process historical orders and deals into EA trades"""

        # Try position-based grouping first
        position_based_tickets = set()

        for position_id in deals_df['position_id'].unique():
            # Process even position_id == 0 trades
            position_deals = deals_df[deals_df['position_id'] == position_id]

            # Find entry and exit deals
            # Entry: entry field == 0 (IN) or type in [0, 1] (BUY/SELL)
            entry_deals = position_deals[position_deals['entry'] == 0]
            exit_deals = position_deals[position_deals['entry'] == 1]

            # If no clear entry deals, try by time (first deal is entry)
            if entry_deals.empty:
                entry_deals = position_deals.iloc[:1]
                if len(position_deals) > 1:
                    exit_deals = position_deals.iloc[1:]

            if entry_deals.empty:
                continue

            entry = entry_deals.iloc[0]

            # Use ticket as unique ID (fallback to position_id if ticket not available)
            ticket = entry.get('ticket', position_id)
            if ticket in position_based_tickets:
                continue  # Already processed
            position_based_tickets.add(ticket)

            # Validate and clean symbol
            symbol = str(entry.get('symbol', '')).strip()
            if not symbol or symbol in ['nan', 'None', '']:
                self.logger.warning(f"Skipping trade {ticket} - invalid symbol: '{symbol}'")
                continue

            trade = EATrade(
                ticket=ticket,
                symbol=symbol,
                trade_type='buy' if entry['type'] == 0 else 'sell',
                entry_time=entry['time'],
                entry_price=entry['price'],
                volume=entry['volume'],
                exit_time=exit_deals.iloc[-1]['time'] if not exit_deals.empty else None,
                exit_price=exit_deals.iloc[-1]['price'] if not exit_deals.empty else None,
                stop_loss=None,
                take_profit=None,
                profit=position_deals['profit'].sum() if not exit_deals.empty else None,
                commission=position_deals['commission'].sum(),
                swap=position_deals['swap'].sum(),
                market_conditions={},  # No historical market data
                magic_number=entry.get('magic'),
                comment=entry.get('comment', '')
            )

            self.known_trades[ticket] = trade

            # Store if closed
            if not exit_deals.empty:
                self._store_ea_trade(trade)

        # FALLBACK: Process any remaining deals that weren't matched by position_id
        # This catches trades where position matching failed
        all_deal_tickets = set(deals_df['ticket'].unique())
        unmatched_tickets = all_deal_tickets - position_based_tickets

        if unmatched_tickets:
            self.logger.info(f"Processing {len(unmatched_tickets)} unmatched deals as individual trades")

            for ticket in unmatched_tickets:
                deal = deals_df[deals_df['ticket'] == ticket].iloc[0]

                # Validate symbol
                symbol = str(deal.get('symbol', '')).strip()
                if not symbol or symbol in ['nan', 'None', '']:
                    self.logger.warning(f"Skipping unmatched deal {ticket} - invalid symbol: '{symbol}'")
                    continue

                # Create trade from single deal
                trade = EATrade(
                    ticket=ticket,
                    symbol=symbol,
                    trade_type='buy' if deal['type'] == 0 else 'sell',
                    entry_time=deal['time'],
                    entry_price=deal['price'],
                    volume=deal['volume'],
                    exit_time=None,  # Unknown exit
                    exit_price=None,
                    stop_loss=None,
                    take_profit=None,
                    profit=deal.get('profit'),
                    commission=deal.get('commission', 0),
                    swap=deal.get('swap', 0),
                    market_conditions={},
                    magic_number=deal.get('magic'),
                    comment=deal.get('comment', '')
                )

                self.known_trades[ticket] = trade

                # Store if has profit (likely closed)
                if deal.get('profit') is not None:
                    self._store_ea_trade(trade)

    def _capture_market_conditions(self, symbol: str,
                                   df: Optional[pd.DataFrame]) -> Dict:
        """
        Capture current market conditions when EA makes a trade

        Args:
            symbol: Trading symbol
            df: Recent price data

        Returns:
            Dictionary of market conditions
        """
        if df is None or df.empty:
            return {}

        latest = df.iloc[-1]

        conditions = {
            'price': latest['close'],
            'high': latest['high'],
            'low': latest['low'],
            'open': latest['open'],
            'time': df.index[-1]
        }

        # Add indicators if available
        for col in ['RSI_14', 'MACD', 'ATR_14', 'BB_percent', 'VWAP']:
            if col in df.columns:
                conditions[col] = latest[col]

        # Recent volatility
        if len(df) >= 20:
            conditions['volatility_20'] = df['close'].pct_change().tail(20).std()

        # Recent trend
        if len(df) >= 50:
            conditions['sma_50'] = df['close'].tail(50).mean()
            conditions['price_vs_sma50'] = latest['close'] / conditions['sma_50']

        return conditions

    def _store_ea_trade(self, trade: EATrade):
        """Store EA trade in database"""
        # Create DataFrame for storage
        trade_data = {
            'ticket': trade.ticket,
            'symbol': trade.symbol,
            'trade_type': trade.trade_type,
            'entry_time': trade.entry_time,
            'entry_price': trade.entry_price,
            'volume': trade.volume,
            'exit_time': trade.exit_time,
            'exit_price': trade.exit_price,
            'stop_loss': trade.stop_loss,
            'take_profit': trade.take_profit,
            'profit': trade.profit,
            'commission': trade.commission,
            'swap': trade.swap,
            'magic_number': trade.magic_number,
            'comment': trade.comment,
            'duration_hours': trade.duration_hours,
            'pips': trade.pips
        }

        # Add market conditions as columns
        for key, value in trade.market_conditions.items():
            trade_data[f'cond_{key}'] = value

        # Store in database (you'll need to add this table to storage.py)
        # For now, just log
        self.logger.info(f"Storing EA trade: {trade.ticket}")

    def get_ea_statistics(self) -> Dict:
        """
        Get statistics about the EA's performance

        Returns:
            Dictionary with EA statistics
        """
        closed_trades = [t for t in self.known_trades.values() if not t.is_open]

        if not closed_trades:
            return {
                'total_trades': 0,
                'open_trades': len([t for t in self.known_trades.values() if t.is_open])
            }

        profits = [t.profit for t in closed_trades if t.profit is not None]
        winning_trades = [p for p in profits if p > 0]
        losing_trades = [p for p in profits if p < 0]

        stats = {
            'total_trades': len(closed_trades),
            'open_trades': len([t for t in self.known_trades.values() if t.is_open]),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(profits) * 100 if profits else 0,
            'total_profit': sum(profits),
            'average_win': sum(winning_trades) / len(winning_trades) if winning_trades else 0,
            'average_loss': sum(losing_trades) / len(losing_trades) if losing_trades else 0,
            'largest_win': max(profits) if profits else 0,
            'largest_loss': min(profits) if profits else 0,
            'average_duration_hours': sum(t.duration_hours for t in closed_trades
                                         if t.duration_hours) / len(closed_trades)
        }

        # Profit factor
        total_wins = sum(winning_trades) if winning_trades else 0
        total_losses = abs(sum(losing_trades)) if losing_trades else 1
        stats['profit_factor'] = total_wins / total_losses if total_losses > 0 else 0

        return stats

    def get_trades_dataframe(self) -> pd.DataFrame:
        """
        Get all EA trades as a DataFrame

        Returns:
            DataFrame with all trades
        """
        trades_data = []

        for trade in self.known_trades.values():
            trade_dict = {
                'ticket': trade.ticket,
                'symbol': trade.symbol,
                'type': trade.trade_type,
                'entry_time': trade.entry_time,
                'entry_price': trade.entry_price,
                'volume': trade.volume,
                'exit_time': trade.exit_time,
                'exit_price': trade.exit_price,
                'profit': trade.profit,
                'pips': trade.pips,
                'duration_hours': trade.duration_hours,
                'is_open': trade.is_open
            }

            # Add market conditions
            for key, value in trade.market_conditions.items():
                trade_dict[f'cond_{key}'] = value

            trades_data.append(trade_dict)

        return pd.DataFrame(trades_data)
