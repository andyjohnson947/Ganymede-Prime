"""
Time-Series Data Storage for Diagnostic Module

Stores and retrieves diagnostic metrics with efficient time-series queries
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path


class DataStore:
    """Persistent storage for diagnostic time-series data"""

    def __init__(self, data_dir: str = "data/diagnostics"):
        """
        Initialize data store

        Args:
            data_dir: Directory for storing diagnostic data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Data files
        self.market_conditions_file = self.data_dir / "market_conditions.json"
        self.trade_performance_file = self.data_dir / "trade_performance.json"
        self.recovery_metrics_file = self.data_dir / "recovery_metrics.json"
        self.hourly_snapshots_file = self.data_dir / "hourly_snapshots.json"

        # Initialize files if they don't exist
        self._ensure_files_exist()

    def _ensure_files_exist(self):
        """Create empty data files if they don't exist"""
        files = [
            self.market_conditions_file,
            self.trade_performance_file,
            self.recovery_metrics_file,
            self.hourly_snapshots_file,
        ]

        for file_path in files:
            if not file_path.exists():
                with open(file_path, 'w') as f:
                    json.dump([], f)

    def _load_json(self, file_path: Path) -> List[Dict]:
        """Load JSON data from file"""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_json(self, file_path: Path, data: List[Dict]):
        """Save JSON data to file"""
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    def record_market_condition(self, symbol: str, condition: Dict):
        """
        Record market condition snapshot

        Args:
            symbol: Trading symbol
            condition: Dict with market metrics (ATR, ADX, trend, etc.)
        """
        data = self._load_json(self.market_conditions_file)

        entry = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            **condition
        }

        data.append(entry)

        # Keep last 7 days only
        cutoff = datetime.now() - timedelta(days=7)
        data = [d for d in data if datetime.fromisoformat(d['timestamp']) > cutoff]

        self._save_json(self.market_conditions_file, data)

    def record_trade(self, trade_data: Dict):
        """
        Record trade open/close with context

        Args:
            trade_data: Dict with trade details and market conditions
        """
        data = self._load_json(self.trade_performance_file)

        entry = {
            'timestamp': datetime.now().isoformat(),
            **trade_data
        }

        data.append(entry)

        # Keep last 30 days
        cutoff = datetime.now() - timedelta(days=30)
        data = [d for d in data if datetime.fromisoformat(d['timestamp']) > cutoff]

        self._save_json(self.trade_performance_file, data)

    def record_recovery_action(self, recovery_data: Dict):
        """
        Record recovery mechanism activation

        Args:
            recovery_data: Dict with recovery details and effectiveness
        """
        data = self._load_json(self.recovery_metrics_file)

        entry = {
            'timestamp': datetime.now().isoformat(),
            **recovery_data
        }

        data.append(entry)

        # Keep last 30 days
        cutoff = datetime.now() - timedelta(days=30)
        data = [d for d in data if datetime.fromisoformat(d['timestamp']) > cutoff]

        self._save_json(self.recovery_metrics_file, data)

    def record_hourly_snapshot(self, snapshot: Dict):
        """
        Record hourly diagnostic snapshot

        Args:
            snapshot: Dict with aggregated metrics
        """
        data = self._load_json(self.hourly_snapshots_file)

        entry = {
            'timestamp': datetime.now().isoformat(),
            **snapshot
        }

        data.append(entry)

        # Keep last 90 days
        cutoff = datetime.now() - timedelta(days=90)
        data = [d for d in data if datetime.fromisoformat(d['timestamp']) > cutoff]

        self._save_json(self.hourly_snapshots_file, data)

    def get_market_conditions(
        self,
        symbol: Optional[str] = None,
        hours: int = 24
    ) -> List[Dict]:
        """
        Get market conditions for analysis

        Args:
            symbol: Optional symbol filter
            hours: Number of hours of history

        Returns:
            List of market condition entries
        """
        data = self._load_json(self.market_conditions_file)

        cutoff = datetime.now() - timedelta(hours=hours)
        data = [d for d in data if datetime.fromisoformat(d['timestamp']) > cutoff]

        if symbol:
            data = [d for d in data if d.get('symbol') == symbol]

        return data

    def get_trades(
        self,
        symbol: Optional[str] = None,
        days: int = 7,
        status: Optional[str] = None
    ) -> List[Dict]:
        """
        Get trade history for analysis

        Args:
            symbol: Optional symbol filter
            days: Number of days of history
            status: Optional status filter ('win', 'loss')

        Returns:
            List of trade entries
        """
        data = self._load_json(self.trade_performance_file)

        cutoff = datetime.now() - timedelta(days=days)
        data = [d for d in data if datetime.fromisoformat(d['timestamp']) > cutoff]

        if symbol:
            data = [d for d in data if d.get('symbol') == symbol]

        if status:
            data = [d for d in data if d.get('status') == status]

        return data

    def get_recovery_actions(
        self,
        recovery_type: Optional[str] = None,
        days: int = 7
    ) -> List[Dict]:
        """
        Get recovery action history

        Args:
            recovery_type: Optional type filter ('grid', 'hedge', 'dca')
            days: Number of days of history

        Returns:
            List of recovery entries
        """
        data = self._load_json(self.recovery_metrics_file)

        cutoff = datetime.now() - timedelta(days=days)
        data = [d for d in data if datetime.fromisoformat(d['timestamp']) > cutoff]

        if recovery_type:
            data = [d for d in data if d.get('type') == recovery_type]

        return data

    def get_hourly_snapshots(self, hours: int = 24) -> List[Dict]:
        """
        Get hourly snapshot history

        Args:
            hours: Number of hours of history

        Returns:
            List of snapshot entries
        """
        data = self._load_json(self.hourly_snapshots_file)

        cutoff = datetime.now() - timedelta(hours=hours)
        data = [d for d in data if datetime.fromisoformat(d['timestamp']) > cutoff]

        return data

    def get_statistics(self) -> Dict:
        """
        Get overall statistics

        Returns:
            Dict with data store statistics
        """
        return {
            'market_conditions_count': len(self._load_json(self.market_conditions_file)),
            'trades_count': len(self._load_json(self.trade_performance_file)),
            'recovery_actions_count': len(self._load_json(self.recovery_metrics_file)),
            'hourly_snapshots_count': len(self._load_json(self.hourly_snapshots_file)),
        }
