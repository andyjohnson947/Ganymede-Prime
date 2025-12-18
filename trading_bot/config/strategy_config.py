"""
Strategy Configuration - Discovered from EA Analysis
All values extracted from 428 trades analyzed
"""

# =============================================================================
# TRADING PARAMETERS
# =============================================================================

# Symbols to trade (from EA analysis - EURUSD primary pair)
SYMBOLS = ['EURUSD']  # Add more symbols as needed: ['EURUSD', 'GBPUSD', 'USDJPY']

# Primary timeframe for trading
TIMEFRAME = 'H1'

# Higher timeframes for institutional levels
HTF_TIMEFRAMES = ['D1', 'W1']

# =============================================================================
# CONFLUENCE PARAMETERS (Discovered from Analysis)
# =============================================================================

# Minimum confluence score required to enter trade
MIN_CONFLUENCE_SCORE = 4

# Optimal confluence score (83.3% win rate)
OPTIMAL_CONFLUENCE_SCORE = 4

# Confluence factor weights (higher = more important)
CONFLUENCE_WEIGHTS = {
    # Primary signals from analysis
    'vwap_band_1': 1,        # Used in 28.0% of trades
    'vwap_band_2': 1,        # Used in 39.5% of trades
    'poc': 1,                # Used in 38.1% of trades
    'swing_low': 1,          # Used in 17.1% of trades
    'swing_high': 1,         # Used in 17.1% of trades
    'above_vah': 1,          # Used in 14.0% of trades
    'below_val': 1,          # Used in 18.7% of trades
    'lvn': 1,                # Used in 16.1% of trades

    # HTF factors (higher weight)
    'prev_day_vah': 2,       # 364 occurrences
    'prev_day_val': 2,       # High importance
    'prev_day_poc': 2,       # 325 occurrences
    'daily_hvn': 2,          # 310 occurrences
    'daily_poc': 2,          # Institutional level
    'weekly_hvn': 3,         # 328 occurrences (highest weight)
    'weekly_poc': 3,         # Strong institutional level
    'prev_week_swing_low': 2,  # 325 occurrences
    'prev_week_swing_high': 2, # Strong resistance
    'prev_week_vwap': 2,     # Weekly pivot
}

# Price tolerance for level detection (0.3% = 30 pips on most pairs)
LEVEL_TOLERANCE_PCT = 0.003

# =============================================================================
# VWAP PARAMETERS
# =============================================================================

# VWAP calculation period (bars)
VWAP_PERIOD = 200  # Approximately 8 days on H1

# Standard deviation multipliers for bands
VWAP_BAND_MULTIPLIERS = [1, 2, 3]  # ±1σ, ±2σ, ±3σ

# =============================================================================
# VOLUME PROFILE PARAMETERS
# =============================================================================

# Number of bins for volume profile
VP_BINS = 100

# Number of HVN/LVN levels to track
HVN_LEVELS = 5
LVN_LEVELS = 5

# Swing high/low detection
SWING_LOOKBACK = 10  # Bars to look back for swing points

# =============================================================================
# TREND FILTER PARAMETERS (ADX + Candle Direction)
# =============================================================================

# Enable trend filtering (prevents trading in strong trends)
TREND_FILTER_ENABLED = True

# ADX parameters
ADX_PERIOD = 14  # Standard ADX period
ADX_THRESHOLD = 25  # Above this = trending market
ADX_STRONG_THRESHOLD = 40  # Above this = strong trend (never trade)

# Candle direction lookback
CANDLE_LOOKBACK = 5  # Number of recent candles to analyze
CANDLE_ALIGNMENT_PCT = 70  # % of candles in same direction = "aligned"

# Trading rules
ALLOW_WEAK_TRENDS = True  # Trade when ADX 20-25 (weak trend)
SKIP_STRONG_TRENDS = True  # Never trade when ADX > 40

# =============================================================================
# GRID TRADING PARAMETERS (AGGRESSIVE RECOVERY SETTINGS)
# =============================================================================

# ⚠️ NOTE: AGGRESSIVE RECOVERY MODE - Higher lot sizes and more levels
# The fix prevents recovery orders from spawning more recovery (300 trade bug fixed)

GRID_ENABLED = True
GRID_SPACING_PIPS = 8  # Tighter spacing: Trigger every 8 pips (was 10.8)
MAX_GRID_LEVELS = 4  # More levels: Maximum 4 grid levels (was 2)
GRID_LOT_SIZE = 0.08  # Matches base for clean partial closes (base + 4 grids = 0.40 lots max)

# =============================================================================
# HEDGING PARAMETERS (AGGRESSIVE RECOVERY SETTINGS)
# =============================================================================

HEDGE_ENABLED = True
HEDGE_TRIGGER_PIPS = 8  # Original: Activate hedge after 8 pips underwater
HEDGE_RATIO = 5.0  # AGGRESSIVE: 5x overhedge for powerful counter-force (was 2.4x)
MAX_HEDGES_PER_POSITION = 1  # Only one hedge per original trade

# =============================================================================
# DCA/MARTINGALE PARAMETERS (OPTIMIZED FROM 413-TRADE ANALYSIS)
# =============================================================================
# Analysis Results: 17 DCA sequences, 82.4% success rate
# Optimal depth: 8 levels (100% success, $98.91 avg profit)
# Best sequence: 8 levels, $229.12 profit, 33 pips decline

DCA_ENABLED = True
DCA_TRIGGER_PIPS = 10  # OPTIMIZED: Trigger every 10 pips (from analysis)
DCA_MAX_LEVELS = 8  # OPTIMIZED: 8 levels proven (100% success in 4/4 sequences)
DCA_MULTIPLIER = 1.49  # OPTIMIZED: Conservative 1.49x (from 8-level analysis, was 2.0x)
DCA_MAX_DRAWDOWN_PIPS = 100  # SAFETY: Allows full 8 levels (L8 @ 80 pips) + 20 pip buffer (was 70, blocked L7-L8)
DCA_MAX_TOTAL_EXPOSURE = 6.0  # SAFETY: Scaled for 0.08 base to allow full 8 levels (0.08→L8 = 5.77 lots)

# =============================================================================
# RISK MANAGEMENT (AGGRESSIVE SETTINGS)
# =============================================================================

# Base lot size for initial positions
BASE_LOT_SIZE = 0.08  # Optimized for partial closes: 50% = 0.04, 25% = 0.02, 25% = 0.02

# Risk per trade (if using dynamic position sizing)
RISK_PERCENT = 1.0

# Use fixed lot size (True) or calculate based on risk % (False)
USE_FIXED_LOT_SIZE = True

# Maximum total exposure across all positions
MAX_TOTAL_LOTS = 23.0  # AGGRESSIVE: Scaled for 8-level DCA (3 positions × ~6.6 lots max each = ~20 lots)

# Maximum exposure per individual recovery stack (parent + all recovery trades)
MAX_STACK_EXPOSURE = 7.0  # SAFETY: Prevents single position from spiraling (base 0.08 + grid + hedge + DCA ≤ 7.0)

# Maximum drawdown before stopping
MAX_DRAWDOWN_PERCENT = 10.0

# Stop loss (if used)
STOP_LOSS_PIPS = None  # EA appears to not use hard stops

# Take profit (if used)
TAKE_PROFIT_PIPS = None  # EA uses VWAP reversion

# =============================================================================
# TIMING PARAMETERS
# =============================================================================

# Trading sessions (discovered from session analysis)
TRADE_SESSIONS = {
    'tokyo': {'start': '00:00', 'end': '09:00', 'enabled': True},
    'london': {'start': '08:00', 'end': '17:00', 'enabled': True},
    'new_york': {'start': '13:00', 'end': '22:00', 'enabled': True},
    'sydney': {'start': '22:00', 'end': '07:00', 'enabled': True},
}

# Days to trade
TRADE_DAYS = [0, 1, 2, 3, 4]  # Monday-Friday

# =============================================================================
# POSITION MANAGEMENT
# =============================================================================

# Maximum open positions
MAX_OPEN_POSITIONS = 3  # Reduced from 10 for safety

# Maximum positions per symbol
MAX_POSITIONS_PER_SYMBOL = 1  # Only 1 position per symbol at a time

# =============================================================================
# EXIT MANAGEMENT (Net Profit Target + Time Limit)
# =============================================================================

# Net profit target for recovery stacks
# Close entire stack (original + grid + hedge + DCA) when combined P&L reaches this
PROFIT_TARGET_PERCENT = 1.0  # Target: ~$10 per trade at $1,023 account (1% of balance)

# Time-based exit for stuck positions
# Auto-close recovery stack after this many hours if still open
MAX_POSITION_HOURS = 12  # AGGRESSIVE: 12 hours max (was 4) - gives recovery time to work

# =============================================================================
# PARTIAL CLOSE SETTINGS (Lock in Profits Incrementally)
# =============================================================================

# Enable/disable partial close mechanism
PARTIAL_CLOSE_ENABLED = True  # Set to True to enable partial profit-taking

# Partial close levels - close portions of stack at profit milestones
# Each level specifies: trigger_percent (% of target profit) and close_percent (% of stack to close)
PARTIAL_CLOSE_LEVELS = [
    {'trigger_percent': 50, 'close_percent': 50},  # At 50% profit ($5), close 50% of stack (0.04 lots)
    {'trigger_percent': 75, 'close_percent': 25},  # At 75% profit ($7.50), close 25% more (0.02 lots)
    # Remaining 25% (0.02 lots) stays open until 100% target ($10) or time limit
]

# Example configurations for different strategies:
#
# Conservative (lock in profits early):
# [
#     {'trigger_percent': 30, 'close_percent': 40},
#     {'trigger_percent': 50, 'close_percent': 30},
#     {'trigger_percent': 75, 'close_percent': 20},
# ]
#
# Aggressive (let more run):
# [
#     {'trigger_percent': 60, 'close_percent': 40},
#     {'trigger_percent': 90, 'close_percent': 40},
# ]
#
# No partial close (original behavior):
# []

# Close order strategy - determines which positions to close first
# Options:
#   'recovery_first': Close grid/DCA/hedge positions first, keep original trade last (recommended)
#   'lifo': Close most recent positions first (Last In First Out)
#   'fifo': Close oldest positions first (First In First Out)
#   'largest_first': Close largest lot sizes first
PARTIAL_CLOSE_ORDER = 'recovery_first'

# =============================================================================
# DATA MANAGEMENT
# =============================================================================

# Historical data bars to load
HISTORY_BARS = {
    'H1': 10000,  # ~416 days
    'D1': 500,    # ~2 years
    'W1': 104,    # ~2 years
}

# Data cache refresh interval (minutes)
DATA_REFRESH_INTERVAL = 60

# =============================================================================
# LOGGING
# =============================================================================

LOG_LEVEL = 'INFO'
LOG_FILE = 'trading_bot.log'
LOG_TRADES = True
LOG_SIGNALS = True

# Enhanced Position Status Logging
STATUS_REPORT_ENABLED = True
STATUS_REPORT_INTERVAL = 30  # Minutes between status reports
LOG_RECOVERY_ACTIONS = True  # Log when grid/hedge/DCA levels are added
LOG_EXIT_PROXIMITY = True    # Alert when approaching profit targets
EXIT_PROXIMITY_PERCENT = 90  # Alert when this % of target reached
CONCISE_FORMAT = True        # Use 3-5 lines per position (vs detailed)
SHOW_MANAGEMENT_TREE = False # Show parent-child recovery trade tree (verbose, use when debugging)
DETECT_ORPHANS = True        # Check for orphaned positions/recovery trades in status reports

# =============================================================================
# BACKTESTING
# =============================================================================

BACKTEST_MODE = False
BACKTEST_START_DATE = '2024-01-01'
BACKTEST_END_DATE = '2024-12-31'
BACKTEST_INITIAL_BALANCE = 10000

# =============================================================================
# SCALPING STRATEGY PARAMETERS
# =============================================================================

# Enable/disable scalping module
SCALPING_ENABLED = False  # Set to True to activate scalping alongside confluence strategy

# Scalping timeframe (M1 = 1 minute, M5 = 5 minutes)
SCALP_TIMEFRAME = 'M1'  # Fast scalping on 1-minute charts

# Scalping lot size (smaller than base for lower risk)
SCALP_LOT_SIZE = 0.01  # Conservative 0.01 lots per scalp

# Position limits
SCALP_MAX_POSITIONS = 3  # Maximum concurrent scalping positions
SCALP_MAX_POSITIONS_PER_SYMBOL = 1  # Only 1 scalp per symbol at a time

# Signal detection parameters
SCALP_MOMENTUM_PERIOD = 14  # RSI and Stochastic period
SCALP_VOLUME_SPIKE_THRESHOLD = 1.5  # Volume must be 1.5x average for spike
SCALP_BREAKOUT_LOOKBACK = 20  # Bars to look back for breakout levels
SCALP_BARS_TO_FETCH = 100  # Historical bars to analyze

# Exit management
SCALP_MAX_HOLD_MINUTES = 10  # Force close after 10 minutes (scalps should be fast)
SCALP_USE_TRAILING_STOP = True  # Enable trailing stop for profitable scalps
SCALP_TRAILING_STOP_PIPS = 5  # Trail stop at 5 pips

# Trading sessions (scalping works best during high volatility)
SCALP_TRADING_SESSIONS = {
    'london': {'start': '08:00', 'end': '12:00', 'enabled': True},  # London open
    'new_york': {'start': '13:00', 'end': '17:00', 'enabled': True},  # NY open
    'overlap': {'start': '13:00', 'end': '16:00', 'enabled': True},  # London/NY overlap (best)
}

# Check interval (how often to scan for signals)
SCALP_CHECK_INTERVAL_SECONDS = 10  # Check every 10 seconds for M1

# Risk-reward ratio (built into signal detector: 2:1 default)
# Stop loss: 5-8 pips based on recent swing
# Take profit: 10-16 pips (2x the stop loss)

# =============================================================================
# MT5 CONNECTION
# =============================================================================

MT5_TIMEOUT = 60000  # 60 seconds
MT5_MAGIC_NUMBER = 987654  # Unique identifier for bot trades
