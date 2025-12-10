"""
Data Collector Module
Orchestrates data collection from MT5 and storage
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd

from ..mt5_connection import MT5ConnectionManager
from .storage import DataStorage


class DataCollector:
    """Collects and stores data from MT5"""

    def __init__(self, mt5_manager: MT5ConnectionManager, storage: DataStorage, config: Dict):
        """
        Initialize Data Collector

        Args:
            mt5_manager: MT5 connection manager instance
            storage: Data storage instance
            config: Configuration dictionary
        """
        self.mt5 = mt5_manager
        self.storage = storage
        self.config = config
        self.logger = logging.getLogger(__name__)

    def collect_historical_data(
        self,
        symbols: Optional[List[str]] = None,
        timeframes: Optional[List[str]] = None,
        bars: int = 10000
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        Collect historical price data for specified symbols and timeframes

        Args:
            symbols: List of symbols (uses config if None)
            timeframes: List of timeframes (uses config if None)
            bars: Number of bars to fetch

        Returns:
            Dictionary of {symbol: {timeframe: DataFrame}}
        """
        if symbols is None:
            symbols = self.config.get('trading', {}).get('symbols', [])

        if timeframes is None:
            timeframes = self.config.get('trading', {}).get('timeframes', [])

        results = {}

        for symbol in symbols:
            results[symbol] = {}

            for timeframe in timeframes:
                self.logger.info(f"Collecting historical data for {symbol} {timeframe}")

                # Fetch data from MT5
                df = self.mt5.get_historical_data(symbol, timeframe, bars=bars)

                if df is not None and not df.empty:
                    # Store in database
                    self.storage.store_price_data(df, symbol, timeframe)
                    results[symbol][timeframe] = df
                    self.logger.info(f"Collected {len(df)} bars for {symbol} {timeframe}")
                else:
                    self.logger.warning(f"No data collected for {symbol} {timeframe}")

        return results

    def collect_historical_orders(
        self,
        days_back: int = 90
    ) -> Optional[pd.DataFrame]:
        """
        Collect historical orders from MT5 account

        Args:
            days_back: Number of days to look back

        Returns:
            DataFrame with historical orders or None
        """
        self.logger.info(f"Collecting historical orders for last {days_back} days")

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        # Fetch from MT5
        df = self.mt5.get_historical_orders(start_date, end_date)

        if df is not None and not df.empty:
            # Store in database
            self.storage.store_historical_orders(df)
            self.logger.info(f"Collected {len(df)} historical orders")
            return df
        else:
            self.logger.warning("No historical orders found")
            return None

    def collect_historical_deals(
        self,
        days_back: int = 90
    ) -> Optional[pd.DataFrame]:
        """
        Collect historical deals from MT5 account

        Args:
            days_back: Number of days to look back

        Returns:
            DataFrame with historical deals or None
        """
        self.logger.info(f"Collecting historical deals for last {days_back} days")

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        # Fetch from MT5
        df = self.mt5.get_historical_deals(start_date, end_date)

        if df is not None and not df.empty:
            # Store in database
            self.storage.store_historical_deals(df)
            self.logger.info(f"Collected {len(df)} historical deals")
            return df
        else:
            self.logger.warning("No historical deals found")
            return None

    def update_recent_data(
        self,
        symbols: Optional[List[str]] = None,
        timeframes: Optional[List[str]] = None,
        bars: int = 100
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        Update with recent data (for continuous collection)

        Args:
            symbols: List of symbols (uses config if None)
            timeframes: List of timeframes (uses config if None)
            bars: Number of recent bars to fetch

        Returns:
            Dictionary of {symbol: {timeframe: DataFrame}}
        """
        self.logger.info("Updating with recent data")
        return self.collect_historical_data(symbols, timeframes, bars)

    def get_latest_data(
        self,
        symbol: str,
        timeframe: str,
        bars: int = 1000
    ) -> Optional[pd.DataFrame]:
        """
        Get latest data for a symbol/timeframe (from DB or MT5)

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            bars: Number of bars to retrieve

        Returns:
            DataFrame with price data or None
        """
        # Try to get from database first
        df = self.storage.get_price_data(symbol, timeframe, limit=bars)

        # If not enough data in DB, fetch from MT5
        if df is None or len(df) < bars:
            self.logger.info(f"Fetching fresh data for {symbol} {timeframe}")
            df = self.mt5.get_historical_data(symbol, timeframe, bars=bars)

            if df is not None:
                self.storage.store_price_data(df, symbol, timeframe)

        return df

    def collect_all_data(self) -> Dict:
        """
        Collect all data types (historical prices, orders, deals)

        Returns:
            Dictionary with collection results
        """
        self.logger.info("Starting full data collection")

        results = {
            'price_data': {},
            'orders': None,
            'deals': None,
            'errors': []
        }

        # Collect historical price data
        try:
            results['price_data'] = self.collect_historical_data()
        except Exception as e:
            self.logger.error(f"Error collecting price data: {e}")
            results['errors'].append(f"Price data: {e}")

        # Collect historical orders
        try:
            results['orders'] = self.collect_historical_orders()
        except Exception as e:
            self.logger.error(f"Error collecting orders: {e}")
            results['errors'].append(f"Orders: {e}")

        # Collect historical deals
        try:
            results['deals'] = self.collect_historical_deals()
        except Exception as e:
            self.logger.error(f"Error collecting deals: {e}")
            results['errors'].append(f"Deals: {e}")

        self.logger.info("Completed full data collection")
        return results

    def cleanup_old_data(self, days: int = 90) -> int:
        """
        Clean up old data from storage

        Args:
            days: Number of days to keep

        Returns:
            Number of rows deleted
        """
        self.logger.info(f"Cleaning up data older than {days} days")
        return self.storage.cleanup_old_data(days)
