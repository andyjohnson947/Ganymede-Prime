"""
Data Storage Module
Handles persistent storage of trading data using SQLite
"""

import sqlite3
import pandas as pd
import logging
from datetime import datetime
from typing import Optional, List
from pathlib import Path


class DataStorage:
    """Manages data storage in SQLite database"""

    def __init__(self, db_path: str = "data/trading_data.db"):
        """
        Initialize Data Storage

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._ensure_database_exists()

    def _ensure_database_exists(self):
        """Create database and tables if they don't exist"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create price data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                time TIMESTAMP NOT NULL,
                [open] REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                [close] REAL NOT NULL,
                tick_volume INTEGER,
                spread INTEGER,
                real_volume REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timeframe, time)
            )
        """)

        # Create historical orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_orders (
                ticket INTEGER PRIMARY KEY,
                time_setup TIMESTAMP NOT NULL,
                time_done TIMESTAMP,
                type INTEGER,
                type_time INTEGER,
                type_filling INTEGER,
                state INTEGER,
                magic INTEGER,
                position_id INTEGER,
                reason INTEGER,
                volume_initial REAL,
                volume_current REAL,
                price_open REAL,
                sl REAL,
                tp REAL,
                price_current REAL,
                price_stoplimit REAL,
                symbol TEXT,
                comment TEXT,
                external_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create historical deals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_deals (
                ticket INTEGER PRIMARY KEY,
                [order] INTEGER,
                time TIMESTAMP NOT NULL,
                type INTEGER,
                entry INTEGER,
                magic INTEGER,
                position_id INTEGER,
                reason INTEGER,
                volume REAL,
                price REAL,
                commission REAL,
                swap REAL,
                profit REAL,
                fee REAL,
                symbol TEXT,
                comment TEXT,
                external_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create daily profiles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                date DATE NOT NULL,
                timeframe TEXT NOT NULL,
                vwap REAL,
                poc REAL,
                vah REAL,
                val REAL,
                total_volume REAL,
                profile_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, date, timeframe)
            )
        """)

        # Create pattern detections table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pattern_detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                pattern_name TEXT NOT NULL,
                detection_time TIMESTAMP NOT NULL,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                confidence REAL,
                direction TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create hypothesis tests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hypothesis_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_name TEXT NOT NULL,
                test_date TIMESTAMP NOT NULL,
                symbol TEXT,
                timeframe TEXT,
                test_type TEXT,
                p_value REAL,
                statistic REAL,
                result TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for better query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_symbol_time ON price_data(symbol, time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_time ON historical_orders(time_setup)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_deals_time ON historical_deals(time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_profiles_date ON daily_profiles(symbol, date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_time ON pattern_detections(detection_time)")

        conn.commit()
        conn.close()
        self.logger.info(f"Database initialized at {self.db_path}")

    def store_price_data(self, df: pd.DataFrame, symbol: str, timeframe: str) -> int:
        """
        Store price data in database

        Args:
            df: DataFrame with OHLCV data (time as index)
            symbol: Trading symbol
            timeframe: Timeframe string

        Returns:
            Number of rows inserted
        """
        try:
            conn = sqlite3.connect(self.db_path)

            # Prepare data
            df_copy = df.copy()
            df_copy['symbol'] = symbol
            df_copy['timeframe'] = timeframe
            df_copy.reset_index(inplace=True)

            # Insert or replace data
            df_copy.to_sql('price_data', conn, if_exists='append', index=False)

            rows_inserted = len(df_copy)
            conn.commit()
            conn.close()

            self.logger.info(f"Stored {rows_inserted} price bars for {symbol} {timeframe}")
            return rows_inserted

        except Exception as e:
            self.logger.error(f"Error storing price data: {e}")
            return 0

    def store_historical_orders(self, df: pd.DataFrame) -> int:
        """
        Store historical orders in database

        Args:
            df: DataFrame with historical orders

        Returns:
            Number of rows inserted
        """
        try:
            conn = sqlite3.connect(self.db_path)

            # Define columns that exist in the database table
            db_columns = [
                'ticket', 'time_setup', 'time_done', 'type', 'type_time',
                'type_filling', 'state', 'magic', 'position_id', 'reason',
                'volume_initial', 'volume_current', 'price_open', 'sl', 'tp',
                'price_current', 'price_stoplimit', 'symbol', 'comment', 'external_id'
            ]

            # Filter DataFrame to only include columns that exist in the database
            df_filtered = df[[col for col in db_columns if col in df.columns]]

            # Insert or replace data
            df_filtered.to_sql('historical_orders', conn, if_exists='append', index=False)

            rows_inserted = len(df_filtered)
            conn.commit()
            conn.close()

            self.logger.info(f"Stored {rows_inserted} historical orders")
            return rows_inserted

        except Exception as e:
            self.logger.error(f"Error storing historical orders: {e}")
            return 0

    def store_historical_deals(self, df: pd.DataFrame) -> int:
        """
        Store historical deals in database

        Args:
            df: DataFrame with historical deals

        Returns:
            Number of rows inserted
        """
        try:
            conn = sqlite3.connect(self.db_path)

            # Define columns that exist in the database table
            db_columns = [
                'ticket', 'order', 'time', 'type', 'entry', 'magic',
                'position_id', 'reason', 'volume', 'price', 'commission',
                'swap', 'profit', 'fee', 'symbol', 'comment', 'external_id'
            ]

            # Filter DataFrame to only include columns that exist in the database
            df_filtered = df[[col for col in db_columns if col in df.columns]]

            df_filtered.to_sql('historical_deals', conn, if_exists='append', index=False)
            rows_inserted = len(df_filtered)
            conn.commit()
            conn.close()

            self.logger.info(f"Stored {rows_inserted} historical deals")
            return rows_inserted

        except Exception as e:
            self.logger.error(f"Error storing historical deals: {e}")
            return 0

    def get_price_data(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> Optional[pd.DataFrame]:
        """
        Retrieve price data from database

        Args:
            symbol: Trading symbol
            timeframe: Timeframe string
            start_time: Start time filter
            end_time: End time filter
            limit: Maximum number of rows to return

        Returns:
            DataFrame with price data or None
        """
        try:
            conn = sqlite3.connect(self.db_path)

            query = "SELECT * FROM price_data WHERE symbol = ? AND timeframe = ?"
            params = [symbol, timeframe]

            if start_time:
                query += " AND time >= ?"
                params.append(start_time)

            if end_time:
                query += " AND time <= ?"
                params.append(end_time)

            query += " ORDER BY time DESC"

            if limit:
                query += f" LIMIT {limit}"

            df = pd.read_sql_query(query, conn, params=params)
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)

            conn.close()
            return df if not df.empty else None

        except Exception as e:
            self.logger.error(f"Error retrieving price data: {e}")
            return None

    def store_daily_profile(self, symbol: str, date: datetime, timeframe: str,
                           vwap: float, poc: float, vah: float, val: float,
                           total_volume: float, profile_data: str = "") -> bool:
        """
        Store daily market profile

        Args:
            symbol: Trading symbol
            date: Date of profile
            timeframe: Timeframe
            vwap: Volume-weighted average price
            poc: Point of control
            vah: Value area high
            val: Value area low
            total_volume: Total volume for the day
            profile_data: Additional profile data (JSON string)

        Returns:
            True if successful
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO daily_profiles
                (symbol, date, timeframe, vwap, poc, vah, val, total_volume, profile_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (symbol, date.date(), timeframe, vwap, poc, vah, val, total_volume, profile_data))

            conn.commit()
            conn.close()

            self.logger.info(f"Stored daily profile for {symbol} on {date.date()}")
            return True

        except Exception as e:
            self.logger.error(f"Error storing daily profile: {e}")
            return False

    def store_pattern_detection(self, symbol: str, timeframe: str, pattern_name: str,
                                detection_time: datetime, confidence: float,
                                direction: str, metadata: str = "") -> bool:
        """
        Store detected pattern

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            pattern_name: Name of detected pattern
            detection_time: When pattern was detected
            confidence: Confidence level (0-1)
            direction: Pattern direction (bullish/bearish)
            metadata: Additional metadata (JSON string)

        Returns:
            True if successful
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO pattern_detections
                (symbol, timeframe, pattern_name, detection_time, confidence, direction, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (symbol, timeframe, pattern_name, detection_time, confidence, direction, metadata))

            conn.commit()
            conn.close()

            self.logger.info(f"Stored pattern detection: {pattern_name} for {symbol}")
            return True

        except Exception as e:
            self.logger.error(f"Error storing pattern detection: {e}")
            return False

    def cleanup_old_data(self, days: int = 90) -> int:
        """
        Remove data older than specified days

        Args:
            days: Number of days to keep

        Returns:
            Number of rows deleted
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cutoff_date = datetime.now() - pd.Timedelta(days=days)

            tables = ['price_data', 'historical_orders', 'historical_deals',
                     'daily_profiles', 'pattern_detections']

            total_deleted = 0
            for table in tables:
                time_col = 'time' if table != 'price_data' else 'time'
                cursor.execute(f"DELETE FROM {table} WHERE {time_col} < ?", (cutoff_date,))
                deleted = cursor.rowcount
                total_deleted += deleted
                self.logger.info(f"Deleted {deleted} old rows from {table}")

            conn.commit()
            conn.close()

            return total_deleted

        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")
            return 0
