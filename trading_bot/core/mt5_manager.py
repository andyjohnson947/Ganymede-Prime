"""
MT5 Connection and Order Management
Handles all MetaTrader 5 operations
"""

import MetaTrader5 as mt5
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import pandas as pd
import time

from config.strategy_config import (
    MT5_TIMEOUT,
    MT5_MAGIC_NUMBER,
    SYMBOLS,
    HISTORY_BARS
)


class MT5Manager:
    """Manages MT5 connection, data fetching, and order execution"""

    def __init__(self, login: int, password: str, server: str):
        """
        Initialize MT5 Manager

        Args:
            login: MT5 account login
            password: MT5 account password
            server: MT5 server name
        """
        self.login = login
        self.password = password
        self.server = server
        self.connected = False
        self.magic_number = MT5_MAGIC_NUMBER

    def connect(self) -> bool:
        """
        Connect to MT5 terminal

        Returns:
            bool: True if connection successful
        """
        if not mt5.initialize():
            print(f"❌ Failed to initialize MT5: {mt5.last_error()}")
            return False

        authorized = mt5.login(self.login, self.password, self.server)

        if not authorized:
            print(f"❌ Failed to login to MT5: {mt5.last_error()}")
            mt5.shutdown()
            return False

        self.connected = True
        account_info = mt5.account_info()
        print(f"✅ Connected to MT5")
        print(f"   Account: {account_info.login}")
        print(f"   Balance: ${account_info.balance:.2f}")
        print(f"   Equity: ${account_info.equity:.2f}")
        print(f"   Server: {account_info.server}")

        return True

    def disconnect(self):
        """Disconnect from MT5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            print("✅ Disconnected from MT5")

    def get_account_info(self) -> Optional[Dict]:
        """
        Get current account information

        Returns:
            Dict with account info or None
        """
        if not self.connected:
            return None

        info = mt5.account_info()
        if info is None:
            return None

        return {
            'balance': info.balance,
            'equity': info.equity,
            'margin': info.margin,
            'free_margin': info.margin_free,
            'margin_level': info.margin_level if info.margin > 0 else 0,
            'profit': info.profit,
            'currency': info.currency
        }

    def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        bars: int = 1000,
        start_date: Optional[datetime] = None
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical OHLCV data

        Args:
            symbol: Trading symbol (e.g., 'EURUSD')
            timeframe: Timeframe string ('H1', 'D1', 'W1', etc.)
            bars: Number of bars to fetch
            start_date: Optional start date

        Returns:
            DataFrame with OHLCV data or None
        """
        if not self.connected:
            print("❌ Not connected to MT5")
            return None

        # Convert timeframe string to MT5 constant
        tf_map = {
            'M1': mt5.TIMEFRAME_M1,
            'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15,
            'M30': mt5.TIMEFRAME_M30,
            'H1': mt5.TIMEFRAME_H1,
            'H4': mt5.TIMEFRAME_H4,
            'D1': mt5.TIMEFRAME_D1,
            'W1': mt5.TIMEFRAME_W1,
            'MN1': mt5.TIMEFRAME_MN1
        }

        tf = tf_map.get(timeframe)
        if tf is None:
            print(f"❌ Invalid timeframe: {timeframe}")
            return None

        # Fetch data
        if start_date:
            rates = mt5.copy_rates_from(symbol, tf, start_date, bars)
        else:
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)

        if rates is None or len(rates) == 0:
            print(f"❌ Failed to fetch data for {symbol} {timeframe}: {mt5.last_error()}")
            return None

        # Convert to DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)

        # Rename columns for consistency
        df.rename(columns={
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'tick_volume': 'volume',
            'real_volume': 'real_volume'
        }, inplace=True)

        print(f"✅ Fetched {len(df)} bars for {symbol} {timeframe}")
        return df

    def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get open positions

        Args:
            symbol: Optional symbol to filter positions

        Returns:
            List of position dictionaries
        """
        if not self.connected:
            return []

        if symbol:
            positions = mt5.positions_get(symbol=symbol)
        else:
            positions = mt5.positions_get()

        if positions is None:
            return []

        result = []
        for pos in positions:
            # Only include positions opened by this bot
            if pos.magic != self.magic_number:
                continue

            result.append({
                'ticket': pos.ticket,
                'symbol': pos.symbol,
                'type': 'buy' if pos.type == mt5.ORDER_TYPE_BUY else 'sell',
                'volume': pos.volume,
                'price_open': pos.price_open,
                'price_current': pos.price_current,
                'profit': pos.profit,
                'sl': pos.sl,
                'tp': pos.tp,
                'time': datetime.fromtimestamp(pos.time),
                'comment': pos.comment
            })

        return result

    def get_all_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get all open positions (including those from other bots/manual trades)

        Unlike get_positions(), this does NOT filter by magic number.
        Use for position adoption during crash recovery.

        Args:
            symbol: Optional symbol to filter positions

        Returns:
            List of position dictionaries
        """
        if not self.connected:
            return []

        if symbol:
            positions = mt5.positions_get(symbol=symbol)
        else:
            positions = mt5.positions_get()

        if positions is None:
            return []

        result = []
        for pos in positions:
            result.append({
                'ticket': pos.ticket,
                'symbol': pos.symbol,
                'type': pos.type,  # Raw MT5 type (0=buy, 1=sell)
                'volume': pos.volume,
                'price_open': pos.price_open,
                'price_current': pos.price_current,
                'profit': pos.profit,
                'sl': pos.sl,
                'tp': pos.tp,
                'time': datetime.fromtimestamp(pos.time),
                'comment': pos.comment,
                'magic': pos.magic  # Include magic number for filtering
            })

        return result

    def place_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = ""
    ) -> Optional[int]:
        """
        Place a market order

        Args:
            symbol: Trading symbol
            order_type: 'buy' or 'sell'
            volume: Lot size
            price: Optional limit price (None for market order)
            sl: Stop loss price
            tp: Take profit price
            comment: Order comment

        Returns:
            Order ticket number or None if failed
        """
        if not self.connected:
            print("❌ Not connected to MT5")
            return None

        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            print(f"❌ Symbol {symbol} not found")
            return None

        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                print(f"❌ Failed to select symbol {symbol}")
                return None

        # Prepare request
        point = symbol_info.point

        if order_type.lower() == 'buy':
            order_type_mt5 = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(symbol).ask if price is None else price
        else:
            order_type_mt5 = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).bid if price is None else price

        # Determine supported filling mode
        filling_type = self._get_filling_mode(symbol_info)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type_mt5,
            "price": price,
            "deviation": 20,
            "magic": self.magic_number,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_type,
        }

        if sl:
            request["sl"] = sl
        if tp:
            request["tp"] = tp

        # Send order
        result = mt5.order_send(request)

        if result is None:
            print(f"❌ Order send failed: {mt5.last_error()}")
            return None

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"❌ Order failed: {result.comment}")
            print(f"   Retcode: {result.retcode}")
            print(f"   Request: {request}")
            return None

        print(f"✅ Order placed: {order_type.upper()} {volume} {symbol} @ {price}")
        print(f"   Ticket: {result.order}")

        return result.order

    def close_position(self, ticket: int, volume: Optional[float] = None) -> bool:
        """
        Close an open position (full or partial)

        Args:
            ticket: Position ticket number
            volume: Volume to close (None = close entire position)

        Returns:
            bool: True if closed successfully
        """
        if not self.connected:
            print("❌ Not connected to MT5")
            return False

        # Get position info
        position = mt5.positions_get(ticket=ticket)
        if not position:
            print(f"❌ Position {ticket} not found")
            return False

        position = position[0]

        # Prepare close request
        symbol = position.symbol
        position_volume = position.volume

        # Determine volume to close
        if volume is None or volume >= position_volume:
            close_volume = position_volume  # Close entire position
            partial_close = False
        else:
            close_volume = volume  # Partial close
            partial_close = True

        # Get symbol info to determine filling mode
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            print(f"❌ Symbol {symbol} not found")
            return False

        # Determine supported filling mode
        filling_type = self._get_filling_mode(symbol_info)

        # Opposite order type
        if position.type == mt5.ORDER_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(symbol).ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": close_volume,
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": self.magic_number,
            # Remove comment field - some brokers reject it on close orders
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_type,
        }

        result = mt5.order_send(request)

        if result is None:
            print(f"❌ Close order failed: {mt5.last_error()}")
            return False

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"❌ Close failed: {result.comment}")
            return False

        if partial_close:
            remaining = position_volume - close_volume
            print(f"✅ Position partially closed: {ticket} ({close_volume}/{position_volume} lots, {remaining} remaining)")
        else:
            print(f"✅ Position closed: {ticket}")
        return True

    def modify_position(
        self,
        ticket: int,
        sl: Optional[float] = None,
        tp: Optional[float] = None
    ) -> bool:
        """
        Modify stop loss or take profit of an open position

        Args:
            ticket: Position ticket number
            sl: New stop loss price (None to keep current)
            tp: New take profit price (None to keep current)

        Returns:
            bool: True if modified successfully
        """
        if not self.connected:
            print("❌ Not connected to MT5")
            return False

        position = mt5.positions_get(ticket=ticket)
        if not position:
            print(f"❌ Position {ticket} not found")
            return False

        position = position[0]

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": position.symbol,
            "position": ticket,
            "sl": sl if sl is not None else position.sl,
            "tp": tp if tp is not None else position.tp,
        }

        result = mt5.order_send(request)

        if result is None:
            print(f"❌ Modify failed: {mt5.last_error()}")
            return False

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"❌ Modify failed: {result.comment}")
            return False

        print(f"✅ Position modified: {ticket}")
        return True

    def _get_filling_mode(self, symbol_info) -> int:
        """
        Determine the best filling mode for the broker

        Args:
            symbol_info: MT5 symbol info object

        Returns:
            int: MT5 filling mode constant
        """
        # Get filling mode flags from symbol
        filling_mode = symbol_info.filling_mode

        # SYMBOL_FILLING_FOK = 1 (bit 0)
        # SYMBOL_FILLING_IOC = 2 (bit 1)
        # SYMBOL_FILLING_RETURN = 4 (bit 2)

        # Check RETURN first (most compatible, used by most brokers)
        if filling_mode & 4:  # Check bit 2
            print(f"Using ORDER_FILLING_RETURN for {symbol_info.name}")
            return mt5.ORDER_FILLING_RETURN

        # Check FOK
        if filling_mode & 1:  # Check bit 0
            print(f"Using ORDER_FILLING_FOK for {symbol_info.name}")
            return mt5.ORDER_FILLING_FOK

        # Check IOC
        if filling_mode & 2:  # Check bit 1
            print(f"Using ORDER_FILLING_IOC for {symbol_info.name}")
            return mt5.ORDER_FILLING_IOC

        # Absolute fallback - try RETURN
        print(f"⚠️ No filling mode detected for {symbol_info.name}, defaulting to RETURN")
        return mt5.ORDER_FILLING_RETURN

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        Get symbol information

        Args:
            symbol: Trading symbol

        Returns:
            Dict with symbol info or None
        """
        info = mt5.symbol_info(symbol)
        if info is None:
            return None

        return {
            'point': info.point,
            'digits': info.digits,
            'spread': info.spread,
            'trade_contract_size': info.trade_contract_size,
            'volume_min': info.volume_min,
            'volume_max': info.volume_max,
            'volume_step': info.volume_step,
        }
