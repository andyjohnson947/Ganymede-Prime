"""
EA Reverse Engineered Trading System
Complete Python implementation of discovered strategy
"""

__version__ = "1.0.0"
__author__ = "EA Analysis Team"

from .trade_manager import TradeManager
from .confluence_analyzer import ConfluenceAnalyzer
from .position_managers import GridManager, HedgeManager, RecoveryManager, Position
from .risk_manager import RiskManager

__all__ = [
    'TradeManager',
    'ConfluenceAnalyzer',
    'GridManager',
    'HedgeManager',
    'RecoveryManager',
    'RiskManager',
    'Position',
]
