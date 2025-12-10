"""
Main Bot Orchestrator
Coordinates all components of the trading bot
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd

from .mt5_connection import MT5ConnectionManager
from .data import DataCollector, DataStorage
from .indicators import IndicatorManager
from .market_profile import MarketProfileCalculator
from .patterns import ReversalPatternDetector
from .hypothesis import HypothesisTester
from .scheduler import TaskScheduler
from .zipline_integration import MT5DataBundle, BacktestEngine


class MT5TradingBot:
    """Main trading bot orchestrator"""

    def __init__(self, config: Dict, credentials: Dict):
        """
        Initialize MT5 Trading Bot

        Args:
            config: Configuration dictionary
            credentials: MT5 credentials dictionary
        """
        self.config = config
        self.credentials = credentials
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self.logger.info("Initializing trading bot components...")

        # MT5 Connection
        self.mt5_manager = MT5ConnectionManager(credentials)

        # Data components
        db_path = config.get('data_collection', {}).get('database_path', 'data/trading_data.db')
        self.storage = DataStorage(db_path)
        self.collector = DataCollector(self.mt5_manager, self.storage, config)

        # Analysis components
        self.indicator_manager = IndicatorManager(config)
        self.profile_calculator = MarketProfileCalculator(
            value_area_percentage=config.get('market_profile', {}).get('value_area_percentage', 70)
        )
        self.pattern_detector = ReversalPatternDetector(
            min_confidence=config.get('patterns', {}).get('min_confidence', 0.65)
        )
        self.hypothesis_tester = HypothesisTester(
            significance_level=config.get('hypothesis_testing', {}).get('significance_level', 0.05)
        )

        # Scheduling
        self.scheduler = TaskScheduler(config)

        # Zipline integration
        self.zipline_bundle = MT5DataBundle(db_path)
        self.backtest_engine = BacktestEngine(config.get('zipline', {}))

        # State
        self.running = False
        self.connected = False

        self.logger.info("Trading bot initialized successfully")

    def start(self) -> bool:
        """
        Start the trading bot

        Returns:
            True if started successfully
        """
        self.logger.info("Starting trading bot...")

        # Connect to MT5
        if not self.mt5_manager.connect():
            self.logger.error("Failed to connect to MT5")
            return False

        self.connected = True
        self.logger.info("Connected to MT5")

        # Initial data collection
        if self.config.get('data_collection', {}).get('enabled', True):
            self.logger.info("Performing initial data collection...")
            self.collector.collect_all_data()

        # Setup scheduled tasks
        self.scheduler.setup_default_tasks(self)
        self.scheduler.start()

        self.running = True
        self.logger.info("Trading bot started successfully")

        return True

    def stop(self):
        """Stop the trading bot"""
        self.logger.info("Stopping trading bot...")

        self.running = False

        # Stop scheduler
        self.scheduler.stop()

        # Disconnect from MT5
        if self.connected:
            self.mt5_manager.disconnect()
            self.connected = False

        self.logger.info("Trading bot stopped")

    def update_data(self):
        """Update data (called by scheduler)"""
        if not self.connected:
            self.logger.warning("Cannot update data - not connected to MT5")
            return

        self.logger.info("Updating data...")
        try:
            self.collector.update_recent_data(bars=100)
            self.logger.info("Data updated successfully")
        except Exception as e:
            self.logger.error(f"Error updating data: {e}")

    def save_daily_profiles(self):
        """Save daily market profiles (called by scheduler)"""
        self.logger.info("Saving daily profiles...")

        symbols = self.config.get('trading', {}).get('symbols', [])
        timeframes = self.config.get('trading', {}).get('timeframes', [])
        today = datetime.now()

        for symbol in symbols:
            for timeframe in timeframes:
                try:
                    # Get data for today
                    df = self.collector.get_latest_data(symbol, timeframe, bars=500)

                    if df is not None and not df.empty:
                        # Calculate profile
                        profile = self.profile_calculator.calculate_daily_profile(df, today)

                        if profile:
                            # Store in database
                            self.storage.store_daily_profile(
                                symbol=symbol,
                                date=today,
                                timeframe=timeframe,
                                vwap=profile.vwap,
                                poc=profile.poc,
                                vah=profile.vah,
                                val=profile.val,
                                total_volume=profile.total_volume
                            )
                            self.logger.info(f"Saved daily profile for {symbol} {timeframe}")

                except Exception as e:
                    self.logger.error(f"Error saving profile for {symbol} {timeframe}: {e}")

        self.logger.info("Daily profiles saved")

    def cleanup_old_data(self, days: int = 90):
        """Clean up old data (called by scheduler)"""
        self.logger.info(f"Cleaning up data older than {days} days...")
        deleted = self.collector.cleanup_old_data(days)
        self.logger.info(f"Deleted {deleted} old records")

    def analyze_symbol(self, symbol: str, timeframe: str = 'H1') -> Dict:
        """
        Perform comprehensive analysis on a symbol

        Args:
            symbol: Trading symbol
            timeframe: Timeframe to analyze

        Returns:
            Dictionary with analysis results
        """
        self.logger.info(f"Analyzing {symbol} {timeframe}...")

        results = {
            'symbol': symbol,
            'timeframe': timeframe,
            'timestamp': datetime.now(),
            'indicators': {},
            'patterns': [],
            'market_profile': None,
            'hypothesis_tests': []
        }

        try:
            # Get data
            df = self.collector.get_latest_data(symbol, timeframe, bars=1000)

            if df is None or df.empty:
                self.logger.warning(f"No data available for {symbol} {timeframe}")
                return results

            # Calculate indicators
            df_with_indicators = self.indicator_manager.calculate_all(df)
            results['indicators'] = {
                name: df_with_indicators[name].iloc[-1]
                for name in self.indicator_manager.get_indicator_names()
                if name in df_with_indicators.columns
            }

            # Detect patterns
            patterns = self.pattern_detector.detect(df)
            results['patterns'] = [
                {
                    'name': p.pattern_name,
                    'confidence': p.confidence,
                    'direction': p.direction,
                    'detected_at': p.end_time
                }
                for p in patterns[-5:]  # Last 5 patterns
            ]

            # Calculate market profile
            profile = self.profile_calculator.calculate_profile(df)
            if profile:
                results['market_profile'] = {
                    'vwap': profile.vwap,
                    'poc': profile.poc,
                    'vah': profile.vah,
                    'val': profile.val,
                    'total_volume': profile.total_volume
                }

            # Hypothesis tests (if enough data)
            if len(df) >= 100:
                df_with_indicators['returns'] = df_with_indicators['close'].pct_change()
                tests = self.hypothesis_tester.run_comprehensive_tests(df_with_indicators)
                results['hypothesis_tests'] = [
                    {
                        'test_name': t.test_name,
                        'result': t.result,
                        'p_value': t.p_value
                    }
                    for t in tests
                ]

            self.logger.info(f"Analysis completed for {symbol} {timeframe}")

        except Exception as e:
            self.logger.error(f"Error analyzing {symbol} {timeframe}: {e}")
            results['error'] = str(e)

        return results

    def run_backtest(
        self,
        symbol: str,
        timeframe: str = 'H1',
        bars: int = 5000
    ) -> Dict:
        """
        Run a simple backtest

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            bars: Number of bars to backtest

        Returns:
            Backtest results dictionary
        """
        self.logger.info(f"Running backtest for {symbol} {timeframe}...")

        try:
            # Get data
            df = self.collector.get_latest_data(symbol, timeframe, bars=bars)

            if df is None or df.empty:
                return {'error': 'No data available'}

            # Calculate indicators
            df = self.indicator_manager.calculate_all(df)

            # Detect patterns
            patterns = self.pattern_detector.detect(df)

            # Create simple signals based on patterns
            signals = pd.Series(0, index=df.index)
            for pattern in patterns:
                if pattern.confidence >= 0.7:
                    signal = 1 if pattern.direction == 'bullish' else -1
                    signals.loc[pattern.end_time:] = signal

            # Run backtest
            results = self.backtest_engine.simple_backtest(
                df=df,
                signals=signals,
                initial_capital=self.config.get('zipline', {}).get('capital_base', 10000)
            )

            self.logger.info("Backtest completed")
            return results

        except Exception as e:
            self.logger.error(f"Error running backtest: {e}")
            return {'error': str(e)}

    def get_status(self) -> Dict:
        """
        Get bot status

        Returns:
            Dictionary with bot status
        """
        status = {
            'running': self.running,
            'connected': self.connected,
            'components': {
                'indicators': len(self.indicator_manager),
                'scheduled_tasks': len(self.scheduler.tasks)
            }
        }

        if self.connected:
            account_info = self.mt5_manager.get_account_info()
            if account_info:
                status['account'] = {
                    'login': account_info.get('login'),
                    'server': account_info.get('server'),
                    'balance': account_info.get('balance')
                }

        return status

    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()
