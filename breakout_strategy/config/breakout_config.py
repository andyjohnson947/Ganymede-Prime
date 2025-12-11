"""
Breakout Strategy Configuration
COMPLETELY SEPARATE from mean reversion module

Based on backtest results from 413 historical trades:
- LVN Breakout in trending markets: 56.8% WR, $5.09 avg profit
- Mean Reversion in trending markets: 62.4% WR, $0.43 avg profit
- Improvement: +1,082% per trade in ADX >= 25 conditions

Optimal confluence score: 6+ (scores 4-5 showed poor performance)
"""

# =============================================================================
# MODULE CONTROL - KILL SWITCHES
# =============================================================================

# Master switch - can disable entire breakout module instantly
BREAKOUT_MODULE_ENABLED = False  # DISABLED by default - enable after testing

# Paper trading mode (logs signals but doesn't execute trades)
BREAKOUT_PAPER_TRADE_ONLY = True  # Start with paper trading

# Performance monitoring - auto-disable if performance degrades
BREAKOUT_AUTO_DISABLE_ENABLED = True
BREAKOUT_MAX_CONSECUTIVE_LOSSES = 3  # Disable after 3 losses in a row
BREAKOUT_MAX_DAILY_LOSS_PCT = 2.0  # Disable if daily loss exceeds 2% of account
BREAKOUT_MIN_WIN_RATE_THRESHOLD = 45  # Disable if WR < 45% over last 20 trades

# =============================================================================
# MARKET CONDITION THRESHOLDS (From ADX Regime Analysis)
# =============================================================================

# ADX thresholds for breakout trading
BREAKOUT_ADX_MIN = 25  # Minimum trending strength (ranging < 25, trending >= 25)
BREAKOUT_ADX_OPTIMAL = 30  # Optimal trending conditions
BREAKOUT_ADX_MAX = 50  # Above this = extreme trend, use conservative entry

# Strong trend handling (ADX >= 40)
ALLOW_STRONG_TREND_BREAKOUTS = True  # Trade when ADX > 40
STRONG_TREND_REQUIRE_PULLBACK = True  # Only take pullback entries in strong trends

# =============================================================================
# LVN BREAKOUT CONFLUENCE SCORING (Optimized from Backtest)
# =============================================================================

# Minimum confluence score to enter (backtest optimal: 6)
# Score 6: 60% WR, $10.90 avg profit
# Score 8-10: 71-100% WR
# Scores 4-5: Poor performance (< 50% WR)
MIN_BREAKOUT_CONFLUENCE = 6

# Confluence factor weights (based on backtest results)
BREAKOUT_CONFLUENCE_WEIGHTS = {
    # LVN Factors (Primary - Low Volume = Low Resistance)
    'at_lvn': 3,  # At low volume node (critical factor)
    'near_lvn': 2,  # Near LVN area (within tolerance)

    # Trend Strength (ADX-based)
    'strong_trend_adx': 2,  # ADX >= 35 (strong trending)
    'trending_adx': 1,  # ADX 25-35 (moderate trending)

    # VWAP Directional Bias (Confirms trend direction)
    'vwap_directional_bias': 2,  # Strong bias (>0.1% from VWAP)
    'vwap_neutral_bias': 1,  # Weak bias (near VWAP)

    # Volume Expansion (Breakout confirmation)
    'high_volume': 2,  # Volume > 70th percentile
    'above_avg_volume': 1,  # Volume > 50th percentile

    # Structure Factors
    'away_from_poc': 1,  # Not stuck in consolidation (POC)
    'vwap_outer_band': 1,  # At ±2σ or ±3σ VWAP band

    # HTF Breakout Factors (optional - for higher conviction)
    'htf_level_breakout': 3,  # Breaking HTF support/resistance
    'vah_val_breakout': 2,  # Breaking value area high/low
}

# LVN detection parameters
LVN_PERCENTILE_THRESHOLD = 30  # Volume must be < 30th percentile to be LVN
LVN_PRICE_TOLERANCE_PCT = 0.002  # 0.2% tolerance for "at LVN" detection

# VWAP bias parameters
VWAP_STRONG_BIAS_PCT = 0.001  # 0.1% distance = strong bias
VWAP_BAND_BREAKOUT_REQUIRED = False  # Don't require VWAP band breakout (LVN is primary)

# Volume expansion thresholds
VOLUME_HIGH_PERCENTILE = 70  # High volume = > 70th percentile
VOLUME_AVG_PERCENTILE = 50  # Above average = > 50th percentile

# =============================================================================
# RISK MANAGEMENT (More Conservative than Mean Reversion)
# =============================================================================

# Position sizing (more conservative due to wider stops)
BREAKOUT_RISK_PERCENT = 0.75  # 0.75% risk per trade (vs 1% for reversion)
BREAKOUT_MAX_EXPOSURE = 4.0  # Max total lots across all breakout positions
BREAKOUT_MAX_POSITIONS = 3  # Max simultaneous breakout positions
BREAKOUT_MAX_POSITIONS_PER_SYMBOL = 1  # Only one breakout per symbol at a time

# Stop loss parameters
BREAKOUT_STOP_LOSS_PIPS = 20  # Default stop loss (wider than reversion)
BREAKOUT_STOP_BELOW_LVN = True  # Place stop below LVN breakout level
BREAKOUT_STOP_ATR_MULTIPLIER = 2.0  # Alternative: 2x ATR stop

# Take profit parameters
BREAKOUT_TP_RATIO = 2.0  # 1:2 risk/reward minimum
BREAKOUT_TP_PIPS = 40  # Default take profit (2x stop)
BREAKOUT_USE_MEASURED_MOVE = True  # Use consolidation range for TP

# Trailing stop parameters
USE_TRAILING_STOP = True
TRAILING_STOP_ACTIVATION_RR = 1.5  # Activate trailing after 1.5x risk in profit
TRAILING_STOP_DISTANCE_ATR = 2.0  # Trail 2 ATR behind price
TRAILING_STOP_DISTANCE_PIPS = 15  # Or 15 pips, whichever is larger

# Breakeven parameters
MOVE_TO_BREAKEVEN = True
BREAKEVEN_TRIGGER_PIPS = 15  # Move stop to BE after 15 pips profit

# =============================================================================
# ENTRY TYPES (Conservative, Aggressive, or Both)
# =============================================================================

# Aggressive entry (immediate breakout)
ALLOW_AGGRESSIVE_ENTRY = False  # Disabled by default (higher risk)
AGGRESSIVE_ENTRY_MIN_CONFLUENCE = 8  # Require very high confluence

# Conservative entry (pullback/retest)
ALLOW_CONSERVATIVE_ENTRY = True  # Enabled (lower risk)
CONSERVATIVE_ENTRY_MIN_CONFLUENCE = 6  # Standard confluence requirement

# Pullback/retest parameters
PULLBACK_MAX_WAIT_BARS = 12  # Wait up to 12 H1 bars (12 hours) for pullback
PULLBACK_TOLERANCE_PIPS = 5  # Must retest within 5 pips of breakout level
PULLBACK_REQUIRE_BOUNCE = True  # Require bullish bounce on retest

# =============================================================================
# EXIT RULES (Trend Exhaustion & Protection)
# =============================================================================

# Trend exhaustion exits
EXIT_ON_ADX_DECLINE = True  # Exit when ADX declining AND < 25
EXIT_ON_OPPOSITE_SIGNAL = True  # Exit if opposite breakout signal appears
EXIT_ON_VWAP_REVERSION = True  # Exit if price reverts through VWAP mean

# Time-based exits
MAX_BREAKOUT_HOLD_HOURS = 72  # Close after 3 days if no movement
MIN_BREAKOUT_HOLD_MINUTES = 60  # Don't exit within first hour (let it develop)

# Profit protection
LOCK_PROFIT_AT_RR = 2.0  # Lock in profit at 1:2 RR (move stop to 1:1)
PARTIAL_CLOSE_ENABLED = False  # Don't use partial closes (keep it simple)

# =============================================================================
# SYMBOL SETTINGS
# =============================================================================

# Symbols to trade with breakout strategy
BREAKOUT_SYMBOLS = ['EURUSD']  # Start with EURUSD only

# Symbol-specific settings (optional overrides)
BREAKOUT_SYMBOL_SETTINGS = {
    'EURUSD': {
        'risk_percent': 0.75,
        'stop_pips': 20,
        'tp_pips': 40,
    },
    # Add more symbols as needed
}

# =============================================================================
# LOGGING & MONITORING
# =============================================================================

# Separate log files for breakout module
LOG_BREAKOUT_SIGNALS = True  # Log all breakout signals
LOG_BREAKOUT_TRADES = True  # Log all breakout trade executions
LOG_BREAKOUT_PERFORMANCE = True  # Log daily performance stats

# Log file names
BREAKOUT_SIGNAL_LOG = 'breakout_signals.log'
BREAKOUT_TRADE_LOG = 'breakout_trades.log'
BREAKOUT_PERFORMANCE_LOG = 'breakout_performance.log'

# =============================================================================
# BACKTESTING & VALIDATION
# =============================================================================

# Backtest mode settings
BACKTEST_MODE = False  # Set to True for historical testing
BACKTEST_START_DATE = '2024-01-01'
BACKTEST_END_DATE = '2024-12-31'

# Validation thresholds (from backtest)
EXPECTED_WIN_RATE_MIN = 55  # Minimum acceptable win rate
EXPECTED_AVG_PROFIT_MIN = 4.0  # Minimum avg profit per trade ($)
EXPECTED_RR_RATIO_MIN = 1.5  # Minimum risk/reward ratio

# =============================================================================
# ADVANCED FEATURES (Future Enhancements)
# =============================================================================

# Multiple timeframe confirmation
USE_MTF_CONFIRMATION = False  # Not implemented yet
MTF_TIMEFRAMES = ['H4', 'D1']  # Higher timeframes to check

# Candle pattern confirmation
REQUIRE_BREAKOUT_CANDLE = False  # Not implemented yet
MIN_BREAKOUT_CANDLE_SIZE = 1.5  # 1.5x average candle range

# News filter
AVOID_NEWS_EVENTS = False  # Not implemented yet
NEWS_BLACKOUT_MINUTES = 30  # Minutes before/after major news

# Session filter
LIMIT_TO_SESSIONS = False  # Not implemented yet
ALLOWED_SESSIONS = ['london', 'newyork']  # Trade only during these sessions

# =============================================================================
# NOTES & WARNINGS
# =============================================================================

"""
IMPORTANT NOTES:

1. **Independent Module**: This breakout strategy is COMPLETELY separate from
   the mean reversion module. They use different market conditions (ADX >= 25
   vs ADX < 25) and never conflict.

2. **Backtested Settings**: All confluence weights and thresholds are based on
   backtest analysis of 413 historical trades. Score 6+ showed 60% WR with
   $10.90 avg profit.

3. **Safety First**: Module is disabled by default. Start with paper trading
   (BREAKOUT_PAPER_TRADE_ONLY = True) before enabling live trades.

4. **Kill Switches**: Multiple safety mechanisms:
   - BREAKOUT_MODULE_ENABLED (master switch)
   - Auto-disable on consecutive losses
   - Auto-disable on win rate degradation

5. **Conservative Risk**: 0.75% risk per trade (vs 1% for reversion) due to
   wider stops required for breakout trading.

6. **Market Condition**: Only trades when ADX >= 25 (trending). Mean reversion
   handles ADX < 25 (ranging). No overlap.

BACKTEST RESULTS SUMMARY:
- Trades: 44 (from 81 signals detected)
- Win Rate: 56.8% (25W / 19L)
- Avg Profit: $5.09 per trade
- Risk/Reward: 1:1.83
- Best Confluence: Score 10 (100% WR, $37.20)
- Optimal Score: 6+ (60% WR, $10.90 avg)

COMPARISON (ADX >= 25 conditions):
- Mean Reversion: $0.43 avg profit
- LVN Breakout: $5.09 avg profit
- Improvement: +1,082% (+$4.66 per trade)
"""
