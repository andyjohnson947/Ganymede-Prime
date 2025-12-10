# Python Trading Platform - EA Parameters Reference

## Quick Parameter List for Implementation

### 1. Entry Strategy Parameters

#### Primary: VWAP Mean Reversion
```python
# VWAP Configuration
VWAP_PERIOD = 'daily'  # or 'session', 'weekly'
VWAP_BAND_1_STDDEV = 1.0  # 1 standard deviation
VWAP_BAND_2_STDDEV = 2.0  # 2 standard deviations
VWAP_BAND_3_STDDEV = 3.0  # 3 standard deviations

# Entry Thresholds
VWAP_ENTRY_BANDS = [1, 2]  # Enter at bands 1 or 2
VWAP_MIN_DEVIATION_PCT = 0.1  # Minimum 0.1% from VWAP
```

#### Market Structure
```python
# Swing Detection
SWING_LOOKBACK_BARS = 100
SWING_PROXIMITY_PCT = 0.001  # Within 0.1% of level

# Support/Resistance
MIN_TOUCHES_FOR_LEVEL = 2
LEVEL_TOLERANCE_PCT = 0.002  # 0.2% tolerance
```

#### Volume Profile
```python
# Volume Profile Settings
VP_NUM_BINS = 50  # Price levels for VP calculation
VP_VALUE_AREA_PCT = 0.70  # 70% value area
VP_POC_TOLERANCE_PCT = 0.002  # 0.2% for POC entries

# Value Area
VA_HIGH_ENTRY_THRESHOLD = True   # Enter when above VAH
VA_LOW_ENTRY_THRESHOLD = True    # Enter when below VAL
```

### 2. Confluence Requirements

```python
# Confluence Scoring
MIN_CONFLUENCE_SCORE = 2  # Require at least 2 factors
HIGH_CONFIDENCE_SCORE = 3  # 3+ factors = high probability

# Confluence Factors (each adds 1 point)
FACTORS = {
    'vwap_band': 1,           # At VWAP band 1 or 2
    'swing_level': 1,         # At swing high/low
    'volume_profile': 1,      # At POC/VAH/VAL
    'order_block': 1,         # At order block
    'previous_day_level': 1,  # At previous day key level
}
```

### 3. Position Sizing & Recovery

#### Base Position Sizing
```python
# Initial Position
INITIAL_LOT_SIZE = 0.01  # Starting lot size
MAX_TOTAL_LOTS = 1.0     # Maximum combined position
RISK_PER_TRADE_PCT = 1.0  # 1% of account per trade
```

#### DCA (Dollar Cost Averaging)
```python
# DCA Settings
DCA_ENABLED = True
DCA_FIXED_LOTS = True  # True = DCA, False = martingale
DCA_LOT_SIZE = 0.01    # Fixed size for each DCA entry
DCA_MAX_ENTRIES = 5    # Maximum DCA entries
DCA_SPACING_PIPS = 50  # Distance between DCA levels
DCA_PRICE_DETERIORATION_MAX_PCT = 2.0  # Stop DCA if >2% loss
```

#### Martingale (if enabled)
```python
# Martingale Settings
MARTINGALE_ENABLED = False  # Use with extreme caution
MARTINGALE_MULTIPLIER = 1.5  # Lot multiplier (1.5x, 2.0x, etc.)
MARTINGALE_MAX_ENTRIES = 3   # Limit depth
MARTINGALE_MAX_LOT = 0.10    # Cap individual lot size
```

#### Grid Trading
```python
# Grid Settings (optional)
GRID_ENABLED = False
GRID_SPACING_PIPS = 20    # Distance between grid levels
GRID_MAX_LEVELS = 5       # Maximum grid positions
GRID_FIXED_LOTS = 0.01    # Lot size per grid level
```

### 4. Hedging Configuration

```python
# Hedge Activation
HEDGE_ENABLED = True
HEDGE_TRIGGER_PIPS = 20           # Open hedge after X pips loss
HEDGE_TRIGGER_DRAWDOWN_PCT = 0.5  # Or after 0.5% drawdown
HEDGE_TIME_WINDOW_MINUTES = 5     # Pair within 5 minutes

# Hedge Sizing
HEDGE_VOLUME_RATIO = 1.0   # 1.0 = full hedge, 1.5 = overhedge
HEDGE_MIN_RATIO = 0.5      # Minimum hedge ratio
HEDGE_MAX_RATIO = 2.0      # Maximum hedge ratio

# Hedge Exit
HEDGE_EXIT_NET_PROFIT_PIPS = 10  # Close both at +10 pips net
HEDGE_ALLOW_PARTIAL_CLOSE = True # Can close one leg first
```

### 5. Risk Management

#### Stop Loss & Take Profit
```python
# TP/SL Mode
TP_SL_MODE = 'atr'  # Options: 'fixed', 'atr', 'structure', 'none'

# Fixed Mode
TP_FIXED_PIPS = 50
SL_FIXED_PIPS = 25

# ATR Mode
TP_ATR_MULTIPLIER = 2.0  # TP = ATR * 2
SL_ATR_MULTIPLIER = 1.0  # SL = ATR * 1
ATR_PERIOD = 14

# Structure Mode (use swing levels)
TP_SWING_TARGET = True   # TP at next swing
SL_SWING_PROTECTION = True  # SL behind last swing

# None Mode (for recovery EAs)
USE_SOFT_STOPS = True    # Mental stops, not hard SL
```

#### Circuit Breakers
```python
# Loss Limits
MAX_CONSECUTIVE_LOSSES = 3
MAX_DAILY_LOSS_USD = 100
MAX_DAILY_LOSS_PCT = 5.0  # 5% of account

# Drawdown Limits
MAX_DRAWDOWN_PCT = 20.0   # Stop all trading at 20% DD
ALERT_DRAWDOWN_PCT = 10.0  # Alert at 10% DD

# Recovery Limits
MAX_RECOVERY_ATTEMPTS = 5
MAX_RECOVERY_DETERIORATION_PCT = 3.0  # Stop recovery beyond 3%
```

### 6. Time Filters

```python
# Trading Hours (UTC)
TRADING_HOURS = {
    'start': 1,   # 01:00 UTC
    'end': 23,    # 23:00 UTC
}

# Avoid Specific Hours
AVOID_HOURS = [0, 23]  # Low liquidity hours

# Session Preferences
PREFER_SESSIONS = ['London', 'New York']  # Best volatility
AVOID_ASIAN_SESSION = False

# Day of Week
AVOID_DAYS = []  # ['Monday', 'Friday'] if needed

# News Filter
AVOID_HIGH_IMPACT_NEWS = True
NEWS_BUFFER_MINUTES = 30  # Avoid 30min before/after news
```

### 7. Technical Indicators

```python
# RSI
RSI_PERIOD = 14
RSI_OVERSOLD = 30   # BUY threshold
RSI_OVERBOUGHT = 70  # SELL threshold

# MACD
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# Moving Averages
SMA_FAST = 20
SMA_SLOW = 50
EMA_PERIOD = 20

# Bollinger Bands
BB_PERIOD = 20
BB_STDDEV = 2.0

# ATR
ATR_PERIOD = 14

# Slope Calculation
SLOPE_LOOKBACK = 5  # Bars for slope calculation
```

### 8. Confluence Factor Weights

```python
# Factor Importance (for ML or scoring)
FACTOR_WEIGHTS = {
    'vwap_band_1': 1.5,        # Highest weight
    'vwap_band_2': 1.5,
    'swing_level': 1.2,
    'poc': 1.3,
    'vah_val': 1.2,
    'order_block': 1.1,
    'prev_day_poc': 1.0,
    'prev_day_vah_val': 0.9,
    'rsi_extreme': 0.8,
    'macd_crossover': 0.7,
}

# Minimum weighted score for entry
MIN_WEIGHTED_CONFLUENCE = 3.0
```

### 9. Order Execution

```python
# Order Type
ORDER_TYPE = 'market'  # or 'limit', 'stop'

# Slippage
MAX_SLIPPAGE_PIPS = 2
RETRY_ON_REQUOTE = True
MAX_RETRIES = 3

# Position Management
ALLOW_MULTIPLE_SYMBOLS = True
MAX_POSITIONS_PER_SYMBOL = 3
MAX_TOTAL_POSITIONS = 10

# Partial Closes
ALLOW_PARTIAL_CLOSE = True
PARTIAL_CLOSE_PCT = 50  # Close 50% at TP1
```

### 10. Monitoring & Logging

```python
# Performance Tracking
TRACK_EQUITY_CURVE = True
LOG_EVERY_TRADE = True
SAVE_TRADE_SCREENSHOTS = False

# Metrics to Track
TRACK_METRICS = [
    'win_rate',
    'profit_factor',
    'sharpe_ratio',
    'max_drawdown',
    'avg_win_loss_ratio',
    'recovery_success_rate',
    'hedge_effectiveness',
    'confluence_win_rate_by_score',
]

# Alerts
SEND_ALERTS = True
ALERT_METHODS = ['telegram', 'email']
ALERT_ON_LOSS_STREAK = 3
ALERT_ON_DRAWDOWN_PCT = 10.0
```

---

## Configuration Template

### Conservative Configuration
```python
config = {
    # Entry
    'vwap_entry_bands': [1, 2],
    'min_confluence': 3,

    # Position Sizing
    'initial_lots': 0.01,
    'dca_enabled': True,
    'dca_fixed_lots': True,
    'martingale_enabled': False,

    # Hedging
    'hedge_enabled': True,
    'hedge_ratio': 1.0,
    'hedge_trigger_pips': 30,

    # Risk
    'tp_atr_mult': 2.0,
    'sl_atr_mult': 1.0,
    'max_consecutive_losses': 3,
    'max_recovery_attempts': 3,

    # Time
    'avoid_hours': [0, 23],
    'prefer_sessions': ['London', 'New York'],
}
```

### Aggressive Configuration
```python
config = {
    # Entry
    'vwap_entry_bands': [1, 2, 3],
    'min_confluence': 2,

    # Position Sizing
    'initial_lots': 0.02,
    'dca_enabled': True,
    'dca_fixed_lots': False,
    'martingale_enabled': True,
    'martingale_multiplier': 1.5,

    # Hedging
    'hedge_enabled': True,
    'hedge_ratio': 1.5,  # Overhedge
    'hedge_trigger_pips': 20,

    # Risk
    'tp_atr_mult': 1.5,
    'sl_atr_mult': 1.5,
    'max_consecutive_losses': 5,
    'max_recovery_attempts': 5,

    # Time
    'avoid_hours': [],
    'prefer_sessions': ['all'],
}
```

### Recovery-Focused Configuration
```python
config = {
    # Entry
    'vwap_entry_bands': [2],  # Only extreme deviations
    'min_confluence': 3,

    # Position Sizing
    'initial_lots': 0.01,
    'dca_enabled': True,
    'dca_fixed_lots': True,
    'dca_max_entries': 7,
    'dca_spacing_pips': 30,

    # Hedging
    'hedge_enabled': True,
    'hedge_ratio': 1.0,
    'hedge_trigger_pips': 50,

    # Risk
    'tp_sl_mode': 'none',  # Rely on mean reversion
    'use_soft_stops': True,
    'max_recovery_attempts': 7,
    'max_recovery_deterioration_pct': 5.0,

    # Time
    'avoid_hours': [0, 1, 22, 23],
    'prefer_sessions': ['London', 'New York'],
}
```

---

## Implementation Priority

### Phase 1: Core Entry Logic (Week 1-2)
1. VWAP calculation with deviation bands
2. Market structure (swing high/low detection)
3. Basic confluence scoring
4. Entry signal generation

### Phase 2: Position Management (Week 3-4)
5. Fixed lot sizing
6. DCA implementation
7. Position tracking and averaging
8. Basic TP/SL

### Phase 3: Risk Management (Week 5-6)
9. Hedging system
10. Circuit breakers
11. Drawdown monitoring
12. Time filters

### Phase 4: Advanced Features (Week 7-8)
13. Volume Profile (POC/VAH/VAL)
14. Order blocks detection
15. Previous day levels
16. Confluence weighting

### Phase 5: Optimization & Testing (Week 9-10)
17. Parameter optimization
18. Backtesting framework
19. Performance analytics
20. Live paper trading

---

## Sample Entry Logic Flow

```python
def should_enter_trade(price_data):
    """
    Complete entry logic based on EA reverse engineering
    """
    confluence_score = 0
    factors = []

    # 1. Check VWAP bands
    vwap_distance = calculate_vwap_distance(price_data)
    if abs(vwap_distance) >= 1.0 and abs(vwap_distance) <= 2.0:
        confluence_score += 1
        factors.append('VWAP Band 1-2')

    # 2. Check swing levels
    at_swing = check_swing_level(price_data)
    if at_swing:
        confluence_score += 1
        factors.append('Swing Level')

    # 3. Check volume profile
    vp_signal = check_volume_profile(price_data)
    if vp_signal in ['at_vah', 'at_val', 'at_poc']:
        confluence_score += 1
        factors.append(f'Volume: {vp_signal}')

    # 4. Check previous day levels
    prev_level = check_previous_day_levels(price_data)
    if prev_level:
        confluence_score += 1
        factors.append(f'Prev Day: {prev_level}')

    # 5. Determine direction
    if confluence_score >= MIN_CONFLUENCE_SCORE:
        direction = 'BUY' if vwap_distance < 0 else 'SELL'

        return {
            'should_trade': True,
            'direction': direction,
            'confluence_score': confluence_score,
            'factors': factors,
            'confidence': confluence_score / 5.0  # Normalize to 0-1
        }

    return {'should_trade': False}
```

---

## Testing Checklist

### Unit Tests
- [ ] VWAP calculation accuracy
- [ ] Swing detection logic
- [ ] Volume profile POC/VAH/VAL
- [ ] Confluence scoring
- [ ] Position sizing calculations
- [ ] Hedge trigger logic
- [ ] DCA average entry calculation

### Integration Tests
- [ ] Entry signal generation
- [ ] Order execution
- [ ] Position management
- [ ] Hedge pairing
- [ ] Recovery sequences
- [ ] TP/SL adjustment
- [ ] Circuit breaker activation

### Backtest Validation
- [ ] Compare with EA historical performance
- [ ] Win rate by confluence level
- [ ] Recovery success rate
- [ ] Hedge effectiveness
- [ ] Drawdown comparison

---

*Parameter reference for Python trading platform based on EA reverse engineering - 2024-12-03*
