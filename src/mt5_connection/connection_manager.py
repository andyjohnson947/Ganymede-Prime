"""
MT5 Connection Manager
Handles all MetaTrader 5 API connections and operations
"""

import MetaTrader5 as mt5
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import time


class MT5ConnectionManager:
    """Manages MT5 connections and provides data access methods"""

    def __init__(self, credentials: Dict[str, any]):
        """
        Initialize MT5 Connection Manager

        Args:
            credentials: Dictionary containing login, password, server, path, timeout
        """
        self.credentials = credentials
        self.connected = False
        self.logger = logging.getLogger(__name__)

    def connect(self) -> bool:
        """
        Establish connection to MT5 terminal

        Tries to connect to already-running MT5 first (preferred)

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Try to connect to already-running MT5 (uses existing login)
            self.logger.info("Connecting to MT5...")

            # Simple initialize - connects to running MT5 without forcing re-login
            if mt5.initialize():
                # Check if we can get account info
                account_info = mt5.account_info()
                if account_info is not None:
                    self.connected = True
                    self.logger.info(f"Connected - Account: {account_info.login}, "
                                   f"Server: {account_info.server}, Balance: ${account_info.balance:,.2f}")
                    return True
                else:
                    self.logger.warning("MT5 running but no account logged in")
                    mt5.shutdown()

            # If that didn't work, MT5 needs to be running and logged in first
            self.logger.error("Could not connect to MT5. Please make sure:")
            self.logger.error("  1. MT5 is running")
            self.logger.error("  2. You are logged into your account in MT5")
            self.logger.error("  3. 'Allow algorithmic trading' is enabled in Tools->Options->Expert Advisors")
            return False

        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from MT5 terminal"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            self.logger.info("Disconnected from MT5")

    def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        bars: int = 1000,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical data from MT5

        Args:
            symbol: Trading symbol (e.g., 'EURUSD')
            timeframe: MT5 timeframe (e.g., 'M15', 'H1', 'D1')
            bars: Number of bars to fetch (if start_date not provided)
            start_date: Start date for data range
            end_date: End date for data range

        Returns:
            DataFrame with OHLCV data or None if error
        """
        if not self.connected:
            self.logger.error("Not connected to MT5")
            return None

        try:
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

            mt5_timeframe = tf_map.get(timeframe)
            if mt5_timeframe is None:
                self.logger.error(f"Invalid timeframe: {timeframe}")
                return None

            # Fetch data based on method
            if start_date and end_date:
                rates = mt5.copy_rates_range(symbol, mt5_timeframe, start_date, end_date)
            elif start_date:
                rates = mt5.copy_rates_from(symbol, mt5_timeframe, start_date, bars)
            else:
                rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, bars)

            if rates is None or len(rates) == 0:
                self.logger.warning(f"No data received for {symbol} {timeframe}")
                return None

            # Convert to DataFrame
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)

            self.logger.info(f"Fetched {len(df)} bars for {symbol} {timeframe}")
            return df

        except Exception as e:
            self.logger.error(f"Error fetching historical data: {e}")
            return None

    def get_historical_orders(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        group: str = ""
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical orders/trades from MT5 account history

        Args:
            start_date: Start date for history range
            end_date: End date for history range
            group: Filter by symbol group (e.g., "*USD*")

        Returns:
            DataFrame with historical orders or None if error
        """
        if not self.connected:
            self.logger.error("Not connected to MT5")
            return None

        try:
            # Use proper datetime objects for MT5 API
            if end_date is None:
                end_date = datetime.now()
            if start_date is None:
                # Fetch ALL history by default
                start_date = datetime(2000, 1, 1)

            self.logger.info(f"Fetching orders from {start_date.date()} to {end_date.date()}")

            # Fetch historical orders
            # Don't pass group parameter if empty - MT5 API bug workaround
            if group and group.strip():
                orders = mt5.history_orders_get(start_date, end_date, group=group)
            else:
                orders = mt5.history_orders_get(start_date, end_date)

            if orders is None:
                self.logger.warning(f"No historical orders found (None returned). Error: {mt5.last_error()}")
                return None

            if len(orders) == 0:
                self.logger.warning("No historical orders found (empty list)")
                return None

            # Convert to DataFrame
            df = pd.DataFrame([order._asdict() for order in orders])
            df['time_setup'] = pd.to_datetime(df['time_setup'], unit='s')
            df['time_done'] = pd.to_datetime(df['time_done'], unit='s')

            # Filter out orders with blank/invalid symbols
            if 'symbol' in df.columns:
                initial_count = len(df)
                df = df[df['symbol'].notna() & (df['symbol'].astype(str).str.strip() != '')]
                filtered_count = initial_count - len(df)
                if filtered_count > 0:
                    self.logger.warning(f"Filtered out {filtered_count} orders with blank symbols")

            self.logger.info(f"Successfully fetched {len(df)} historical orders!")
            return df

        except Exception as e:
            self.logger.error(f"Error fetching historical orders: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    def get_historical_deals(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        group: str = ""
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical deals from MT5 account history

        Args:
            start_date: Start date for history range
            end_date: End date for history range
            group: Filter by symbol group

        Returns:
            DataFrame with historical deals or None if error
        """
        if not self.connected:
            self.logger.error("Not connected to MT5")
            return None

        try:
            # Use proper datetime objects for MT5 API
            if end_date is None:
                end_date = datetime.now()
            if start_date is None:
                # Fetch ALL history by default (from 2000 to now)
                start_date = datetime(2000, 1, 1)

            self.logger.info(f"Fetching deals from {start_date.date()} to {end_date.date()}")

            # Fetch all deals in date range
            # Don't pass group parameter if empty - MT5 API bug workaround
            if group and group.strip():
                deals = mt5.history_deals_get(start_date, end_date, group=group)
            else:
                deals = mt5.history_deals_get(start_date, end_date)

            if deals is None:
                self.logger.warning(f"No historical deals found (None returned). Error: {mt5.last_error()}")
                return None

            if len(deals) == 0:
                self.logger.warning("No historical deals found (empty list)")
                return None

            df = pd.DataFrame([deal._asdict() for deal in deals])
            df['time'] = pd.to_datetime(df['time'], unit='s')

            # Filter out deals with blank/invalid symbols
            if 'symbol' in df.columns:
                initial_count = len(df)
                df = df[df['symbol'].notna() & (df['symbol'].astype(str).str.strip() != '')]
                filtered_count = initial_count - len(df)
                if filtered_count > 0:
                    self.logger.warning(f"Filtered out {filtered_count} deals with blank symbols")

            self.logger.info(f"Successfully fetched {len(df)} historical deals!")
            return df

        except Exception as e:
            self.logger.error(f"Error fetching historical deals: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    def get_symbols(self) -> List[str]:
        """
        Get list of available trading symbols

        Returns:
            List of symbol names
        """
        if not self.connected:
            self.logger.error("Not connected to MT5")
            return []

        try:
            symbols = mt5.symbols_get()
            if symbols is None:
                return []

            return [symbol.name for symbol in symbols if symbol.visible]

        except Exception as e:
            self.logger.error(f"Error fetching symbols: {e}")
            return []

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        Get symbol information

        Args:
            symbol: Trading symbol

        Returns:
            Dictionary with symbol info or None
        """
        if not self.connected:
            self.logger.error("Not connected to MT5")
            return None

        try:
            info = mt5.symbol_info(symbol)
            if info is None:
                return None

            return info._asdict()

        except Exception as e:
            self.logger.error(f"Error fetching symbol info: {e}")
            return None

    def get_account_info(self) -> Optional[Dict]:
        """
        Get current account information

        Returns:
            Dictionary with account info or None
        """
        if not self.connected:
            self.logger.error("Not connected to MT5")
            return None

        try:
            info = mt5.account_info()
            if info is None:
                return None

            return info._asdict()

        except Exception as e:
            self.logger.error(f"Error fetching account info: {e}")
            return None

    def get_terminal_info(self) -> Optional[Dict]:
        """
        Get MT5 terminal information

        Returns:
            Dictionary with terminal info or None
        """
        if not self.connected:
            self.logger.error("Not connected to MT5")
            return None

        try:
            info = mt5.terminal_info()
            if info is None:
                return None

            return info._asdict()

        except Exception as e:
            self.logger.error(f"Error fetching terminal info: {e}")
            return None

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
