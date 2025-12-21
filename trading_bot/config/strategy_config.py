"""
Strategy Configuration - Discovered from EA Analysis
All values extracted from 428 trades analyzed
"""

# =============================================================================
# TRADING PARAMETERS
# =============================================================================

# Symbols to trade
SYMBOLS = []  # Will be loaded from analysis

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
GRID_LOT_SIZE = 0.04  # Updated grid lot size to 0.04 per level

# =============================================================================
# HEDGING PARAMETERS (AGGRESSIVE RECOVERY SETTINGS)
# =============================================================================

HEDGE_ENABLED = True
HEDGE_TRIGGER_PIPS = 8  # Original: Activate hedge after 8 pips underwater
HEDGE_RATIO = 5.0  # AGGRESSIVE: 5x overhedge for powerful counter-force (was 2.4x)
MAX_HEDGES_PER_POSITION = 1  # Only one hedge per original trade

# =============================================================================
# DCA/MARTINGALE PARAMETERS (AGGRESSIVE RECOVERY SETTINGS)
# =============================================================================

DCA_ENABLED = True
DCA_TRIGGER_PIPS = 20  # Faster trigger: Start averaging down after 20 pips (was 25)
DCA_MAX_LEVELS = 4  # More levels: 4 DCA levels max (was 2)
DCA_MULTIPLIER = 2.0  # AGGRESSIVE: 2x martingale scaling (was 1.5x) - doubles each level

# =============================================================================
# RISK MANAGEMENT (AGGRESSIVE SETTINGS)
# =============================================================================

# Base lot size for initial positions
BASE_LOT_SIZE = 0.04  # Updated to 0.04 (was 0.03)

# Risk per trade (if using dynamic position sizing)
RISK_PERCENT = 1.0

# Use fixed lot size (True) or calculate based on risk % (False)
USE_FIXED_LOT_SIZE = True

# Maximum total exposure across all positions
MAX_TOTAL_LOTS = 15.0  # AGGRESSIVE: Increased from 5.04 to accommodate larger recovery stacks

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
PROFIT_TARGET_PERCENT = 0.5  # AGGRESSIVE: 0.5% target (easier to hit with larger lots)

# Time-based exit for stuck positions
# Auto-close recovery stack after this many hours if still open
MAX_POSITION_HOURS = 12  # AGGRESSIVE: 12 hours max (was 4) - gives recovery time to work

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

# =============================================================================
# BACKTESTING
# =============================================================================

BACKTEST_MODE = False
BACKTEST_START_DATE = '2024-01-01'
BACKTEST_END_DATE = '2024-12-31'
BACKTEST_INITIAL_BALANCE = 10000

# =============================================================================
# MT5 CONNECTION
# =============================================================================

MT5_TIMEOUT = 60000  # 60 seconds
MT5_MAGIC_NUMBER = 987654  # Unique identifier for bot trades
