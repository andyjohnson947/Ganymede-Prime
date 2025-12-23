"""
Strategy Configuration - Discovered from EA Analysis
All values extracted from 428 trades analyzed
"""

# =============================================================================
# TRADING PARAMETERS
# =============================================================================

# Symbols to trade (EURUSD and GBPUSD only based on analysis)
SYMBOLS = ['EURUSD', 'GBPUSD']

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
BASE_LOT_SIZE = 0.04  # Updated to 0.04 with partial close strategy

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
# TIME FILTERS - STRATEGY-SPECIFIC TRADING WINDOWS
# =============================================================================

# Enable time filtering (False = trade all hours)
ENABLE_TIME_FILTERS = True

# =============================================================================
# BROKER TIMEZONE CONFIGURATION
# =============================================================================

# MT5 brokers use different server timezones. Set your broker's GMT offset here.
# This is CRITICAL for time filters to work correctly!
#
# Common broker timezones:
#   0  = GMT/UTC (rare, used by some brokers)
#   +2 = GMT+2 (EET - most European brokers in winter)
#   +3 = GMT+3 (EET summer / some brokers use this year-round)
#   -4 = GMT-4 (EDT - some US brokers in summer)
#   -5 = GMT-5 (EST - some US brokers in winter)
#
# HOW TO FIND YOUR BROKER'S OFFSET:
# 1. Check current GMT time: https://time.is/GMT
# 2. Check your MT5 terminal time (bottom right corner)
# 3. Calculate: MT5 time - GMT time = your offset
#    Example: MT5 shows 14:00, GMT is 12:00 → offset is +2
#
# IMPORTANT: All trading hours in this config are in GMT/UTC.
# The bot will automatically convert broker time to GMT using this offset.
BROKER_GMT_OFFSET = 0  # SET THIS TO YOUR BROKER'S OFFSET!

# =============================================================================

# MEAN REVERSION TRADING HOURS (GMT/UTC)
# Based on analysis: Best win rates (79.3% at Value Area, 73.5% at VWAP ±2σ)
# Hours with highest success: 05:00 (100%), 12:00 (100%), 07:00 (93%), 06:00 (86%), 09:00 (80%)
MEAN_REVERSION_HOURS = [5, 6, 7, 9, 12]

# MEAN REVERSION TRADING DAYS (0=Monday, 6=Sunday)
# Best days: Tuesday (73%), Wednesday (70%), Thursday (69%)
# Monday included per user request
MEAN_REVERSION_DAYS = [0, 1, 2, 3]  # Mon, Tue, Wed, Thu

# MEAN REVERSION SESSIONS
# Tokyo: 74% win rate, London early: 68% win rate
# Avoid New York: 53% win rate
MEAN_REVERSION_SESSIONS = ['tokyo', 'london']

# BREAKOUT TRADING HOURS (UTC)
# Based on analysis: High volatility periods
# Hours: 03:00 (70% win, high ATR), 14:00 (London/NY overlap)
BREAKOUT_HOURS = [3, 14, 15, 16]  # 03:00 and 14:00-16:00 (London/NY overlap)

# BREAKOUT TRADING DAYS
# Best days: Tuesday (62% win, high volatility), Friday (trend exhaustion)
# Monday (week open breakouts)
BREAKOUT_DAYS = [0, 1, 4]  # Mon, Tue, Fri

# BREAKOUT SESSIONS
# London/NY overlap = highest volatility for breakouts
# Tokyo included for 03:00 breakout hour (70% win rate in analysis)
BREAKOUT_SESSIONS = ['tokyo', 'london', 'new_york']

# =============================================================================
# BREAKOUT STRATEGY PARAMETERS
# =============================================================================

# Enable breakout strategy (in addition to mean reversion)
BREAKOUT_ENABLED = True

# Breakout detection parameters
BREAKOUT_LOOKBACK = 20  # Bars to identify range high/low
BREAKOUT_VOLUME_MULTIPLIER = 1.5  # Volume must be 1.5x average
BREAKOUT_ATR_MULTIPLIER = 1.2  # ATR must be 1.2x median (high volatility)

# Breakout entry conditions
BREAKOUT_MIN_RANGE_PIPS = 20  # Minimum range size to consider for breakout
BREAKOUT_CLOSE_BEYOND_LEVEL = True  # Candle must close beyond level (not just wick)

# Breakout momentum filters
BREAKOUT_RSI_BUY_THRESHOLD = 60  # RSI > 60 for bullish breakouts
BREAKOUT_RSI_SELL_THRESHOLD = 40  # RSI < 40 for bearish breakouts

# Breakout position sizing (more conservative due to lower win rate)
BREAKOUT_LOT_SIZE_MULTIPLIER = 0.5  # Use 50% of normal lot size

# Breakout profit targets
BREAKOUT_TARGET_METHOD = 'range_projection'  # 'range_projection', 'atr_multiple', 'lvn'
BREAKOUT_TARGET_MULTIPLIER = 1.0  # 1x range for 'range_projection'
BREAKOUT_ATR_TARGET_MULTIPLE = 2.0  # 2x ATR for 'atr_multiple'

# Breakout stop loss (tight stops - breakouts should not reverse)
BREAKOUT_STOP_PERCENT = 0.2  # 20% of range back from breakout level

# =============================================================================
# POSITION MANAGEMENT
# =============================================================================

# Maximum open positions
MAX_OPEN_POSITIONS = 3  # Reduced from 10 for safety

# Maximum positions per symbol
MAX_POSITIONS_PER_SYMBOL = 1  # Only 1 position per symbol at a time

# =============================================================================
# EXIT MANAGEMENT (Net Profit Target + Time Limit + Partial Close)
# =============================================================================

# Net profit target for recovery stacks
# Close entire stack (original + grid + hedge + DCA) when combined P&L reaches this
PROFIT_TARGET_PERCENT = 0.5  # AGGRESSIVE: 0.5% target (easier to hit with larger lots)

# Time-based exit for stuck positions
# Auto-close recovery stack after this many hours if still open
MAX_POSITION_HOURS = 12  # AGGRESSIVE: 12 hours max (was 4) - gives recovery time to work

# =============================================================================
# PARTIAL CLOSE (SCALE OUT) SETTINGS
# =============================================================================

# Enable partial close functionality
PARTIAL_CLOSE_ENABLED = True

# Partial close levels (percentage of position to close at each milestone)
# Closes portions of the position as it moves toward TP
PARTIAL_CLOSE_LEVELS = [
    {'percent_to_tp': 50, 'close_percent': 50},  # Close 50% at halfway to TP
    {'percent_to_tp': 75, 'close_percent': 50},  # Close 50% of remaining (25% total) at 75% to TP
    # Final 25% closes at 100% TP or VWAP reversion
]

# Minimum profit required to enable partial close (in pips)
# Prevents partial close on small moves
PARTIAL_CLOSE_MIN_PROFIT_PIPS = 10

# Apply partial close to recovery stacks (grid/hedge/DCA)
PARTIAL_CLOSE_RECOVERY = False  # Only apply to original positions

# Trail stop on remaining position after first partial close
TRAIL_STOP_AFTER_PARTIAL = True
TRAIL_STOP_DISTANCE_PIPS = 15  # Trail stop 15 pips behind price

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
