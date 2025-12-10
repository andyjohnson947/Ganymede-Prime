"""
Trading System Configuration
All parameters discovered from EA reverse engineering
"""

# ==============================================================================
# BROKER LOT SETTINGS
# ==============================================================================
MIN_LOT_SIZE = 0.01               # Minimum lot size (broker dependent)
MAX_LOT_SIZE = 100.0              # Maximum lot size (broker dependent)
LOT_STEP = 0.01                   # Lot size step (usually 0.01)

# ==============================================================================
# GRID CONFIGURATION
# ==============================================================================
GRID_SPACING_PIPS = 10.8          # Distance between grid levels
MAX_GRID_LEVELS = 6               # Maximum grid positions
GRID_BASE_LOT_SIZE = 0.02         # Fixed lot size per grid level (changed from 0.01)

# ==============================================================================
# HEDGE CONFIGURATION
# ==============================================================================
HEDGE_ENABLED = True              # Enable hedging
HEDGE_RATIO = 2.4                 # Overhedge ratio (2.4x original position)
HEDGE_TRIGGER_PIPS = 8            # Trigger hedge after X pips underwater (very aggressive protection)
HEDGE_TIME_WINDOW_MINUTES = 5     # Pair hedge within X minutes

# ==============================================================================
# RECOVERY CONFIGURATION
# ==============================================================================
RECOVERY_ENABLED = True           # Enable martingale recovery
MAX_RECOVERY_LEVELS = 5           # Maximum recovery attempts (not 21!)
MARTINGALE_MULTIPLIER = 1.4       # Lot size multiplier per recovery level
MAX_TOTAL_LEVELS = 11             # Grid (6) + Recovery (5)

# ==============================================================================
# CONFLUENCE REQUIREMENTS
# ==============================================================================
MIN_CONFLUENCE_SCORE = 4          # Minimum factors required for entry
HIGH_CONFIDENCE_SCORE = 7         # Score for high-confidence trades
CONFLUENCE_TOLERANCE_PCT = 0.003  # 0.3% tolerance for level matching

# ==============================================================================
# VWAP CONFIGURATION
# ==============================================================================
VWAP_PERIOD = 'daily'             # VWAP calculation period
VWAP_BAND_1_STDDEV = 1.0          # 1 standard deviation
VWAP_BAND_2_STDDEV = 2.0          # 2 standard deviations
VWAP_BAND_3_STDDEV = 3.0          # 3 standard deviations
VWAP_ENTRY_BANDS = [1, 2]         # Enter at bands 1 or 2

# ==============================================================================
# VOLUME PROFILE CONFIGURATION
# ==============================================================================
VP_NUM_BINS = 50                  # Price levels for volume profile
VP_VALUE_AREA_PCT = 0.70          # 70% value area
VP_LOOKBACK_BARS = 100            # Bars for volume profile calculation

# ==============================================================================
# MARKET STRUCTURE CONFIGURATION
# ==============================================================================
SWING_LOOKBACK_BARS = 100         # Bars for swing high/low detection
SWING_PROXIMITY_PCT = 0.001       # 0.1% tolerance for swing levels
ORDER_BLOCK_VOLUME_PERCENTILE = 0.8  # Top 20% volume for order blocks

# ==============================================================================
# RISK MANAGEMENT
# ==============================================================================
MAX_DRAWDOWN_PCT = 10.0           # Stop trading at 10% drawdown
MAX_DAILY_LOSS_PCT = 5.0          # Daily loss limit
MAX_CONSECUTIVE_LOSSES = 5        # Stop after X consecutive losses
RISK_PER_TRADE_PCT = 1.0          # Risk 1% per trade

# ==============================================================================
# POSITION LIMITS
# ==============================================================================
MAX_POSITIONS_PER_SYMBOL = 20     # Maximum concurrent positions
MAX_TOTAL_POSITIONS = 50          # Maximum total positions
MAX_EXPOSURE_LOTS = 1.0           # Maximum lot exposure

# ==============================================================================
# TIME FILTERS
# ==============================================================================
AVOID_HOURS = [0, 23]             # Hours to avoid (low liquidity)
PREFER_SESSIONS = ['London', 'New York']  # Best sessions
TRADING_START_HOUR = 1            # Start trading at 01:00 UTC
TRADING_END_HOUR = 23             # Stop trading at 23:00 UTC

# ==============================================================================
# TREND FILTER
# ==============================================================================
MAX_TREND_STRENGTH_PCT = 1.0      # Avoid trades if trend > 1% (ranging only!)
TREND_LOOKBACK_BARS = 50          # Bars for trend calculation

# ==============================================================================
# TP/SL CONFIGURATION
# ==============================================================================
TAKE_PROFIT_PIPS = 60.0           # Take profit distance in pips (configurable)
STOP_LOSS_PIPS = 30.0             # Stop loss distance in pips
USE_HARD_SL = False               # Don't use hard SL (rely on grid/hedge)
USE_SOFT_STOPS = True             # Use mental stops
TP_MODE = 'vwap_reversion'        # TP when price returns to VWAP
BREAKEVEN_ENABLED = True          # Move to breakeven when profitable

# ==============================================================================
# EXECUTION SETTINGS
# ==============================================================================
MAX_SLIPPAGE_PIPS = 2             # Maximum acceptable slippage
ORDER_RETRY_ATTEMPTS = 3          # Retry failed orders
ORDER_TIMEOUT_SECONDS = 5         # Order execution timeout

# ==============================================================================
# LOGGING AND MONITORING
# ==============================================================================
LOG_LEVEL = 'INFO'                # DEBUG, INFO, WARNING, ERROR
SAVE_TRADE_SCREENSHOTS = False    # Save chart screenshots
SEND_TELEGRAM_ALERTS = False      # Send Telegram notifications
ALERT_ON_DRAWDOWN_PCT = 8.0       # Alert at 8% drawdown

# ==============================================================================
# PREVIOUS DAY LEVELS
# ==============================================================================
CALC_PREV_DAY_LEVELS = True       # Calculate previous day POC/VAH/VAL/VWAP/LVN
PREV_DAY_LOOKBACK_DAYS = 5        # Look back up to 5 days (weekends)

# ==============================================================================
# SYMBOL SETTINGS
# ==============================================================================
DEFAULT_SYMBOL = 'EURUSD'
ALLOWED_SYMBOLS = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD']
POINT_VALUE = 0.0001              # Pip value (0.0001 for most pairs)

# ==============================================================================
# DEMO TESTING
# ==============================================================================
DEMO_MODE = True                  # Start in demo mode
PAPER_TRADING = False             # Simulate without real MT5 orders
INITIAL_BALANCE = 10000.0         # Demo account balance


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
def normalize_lot_size(lot_size: float) -> float:
    """
    Normalize lot size to broker's valid increments
    
    Args:
        lot_size: Raw calculated lot size
        
    Returns:
        Normalized lot size that broker will accept
        
    Example:
        0.024 -> 0.02 (rounded down to nearest 0.01)
        0.028 -> 0.03 (rounded to nearest 0.01)
    """
    # Round to nearest lot step
    normalized = round(lot_size / LOT_STEP) * LOT_STEP
    
    # Ensure within broker limits
    normalized = max(MIN_LOT_SIZE, min(normalized, MAX_LOT_SIZE))
    
    # Round to 2 decimal places to avoid floating point issues
    return round(normalized, 2)
