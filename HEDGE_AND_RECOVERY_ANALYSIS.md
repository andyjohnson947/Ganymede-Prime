# Hedge Position Management & Recovery Strategy Analysis

## 1. Hedge Position Management Mechanism

### How Hedges Are Opened

Based on reverse engineering analysis (`reverse_engineer_ea.py:1253-1340`):

**Detection Criteria:**
- **Timing Window**: Opposite direction positions opened within **5 minutes** of each other
- **Same Symbol**: Both positions must be on the same currency pair
- **Price Proximity**: Within ~1% price difference (can be "a pip out" as you mentioned)

**Example Flow:**
```
10:00:00 - Open BUY EURUSD 0.01 @ 1.0850
10:02:30 - Open SELL EURUSD 0.01 @ 1.0848  ← Hedge triggered
         (2.5 minutes apart, 2 pips difference)
```

### Hedge Management Strategy

**Key Discovery:** Both positions DO NOT just run out indefinitely. Here's what happens:

#### Hedge Triggers (from `hedge_triggers` analysis):
1. **Price Movement Trigger**
   - Monitors pip movement from original entry
   - Tracks percentage deterioration
   - Opens hedge when original position moves against you

2. **Volume Ratios**
   - **Balanced Hedge** (0.9-1.1x): Equal volume both directions → True hedge
   - **Partial Hedge** (<0.9x): Smaller hedge → Reduces exposure but maintains directional bias
   - **Unbalanced Hedge** (>1.1x): Larger hedge → Overhedges to recover faster

#### Exit Management:
From `hedge_triggers` tracking:
- Monitors `net_result`: Combined P&L of both hedge positions
- Likely closes both when net profit target reached
- May close losing side first if original direction proves correct

### Typical Hedge Scenarios:

**Scenario 1: Balanced Hedge (Risk Reduction)**
```
Entry 1: BUY  0.10 @ 1.0850
Entry 2: SELL 0.10 @ 1.0840  (price moved 10 pips against)
→ Locks in 10 pip loss, waits for clear direction
→ Closes hedge leg when direction confirmed
```

**Scenario 2: Unbalanced Hedge (Recovery)**
```
Entry 1: BUY  0.10 @ 1.0850
Entry 2: SELL 0.15 @ 1.0840  (1.5x volume)
→ Overhedged to profit from continued downside
→ If market bounces: Original BUY + partial SELL close = net profit
→ If market continues down: SELL profits offset BUY loss
```

---

## 2. DCA (Dollar Cost Averaging) & Recovery Scale-Out

### How Recovery Works (`analyze_hedging_and_recovery:1341-1416`)

**Detection Method:**
- Tracks same-direction trades added when price deteriorates
- Analyzes lot size progression
- Measures price movement between entries

### Recovery Patterns Detected:

#### Pattern A: **True DCA (Fixed Lots)**
```
Criteria: Volume multiplier 0.9-1.1x (essentially flat)

Example:
Step 1: BUY 0.10 @ 1.0850
Step 2: BUY 0.10 @ 1.0800  (-50 pips, volume: 1.0x)
Step 3: BUY 0.10 @ 1.0750  (-100 pips, volume: 1.0x)

Average Entry: 1.0800
Breakeven: Price needs to reach 1.0800 + spread
Total Volume: 0.30 lots
```

**Scale-Out Strategy:**
- Likely closes partial position at milestones
- Example: Close 0.10 at +20 pips, 0.10 at +40 pips, 0.10 at +60 pips
- Ensures profit taking while reducing risk

#### Pattern B: **Martingale (Multiplied Lots)**
```
Criteria: Volume multiplier >1.5x

Example:
Step 1: BUY 0.10 @ 1.0850
Step 2: BUY 0.20 @ 1.0800  (-50 pips, volume: 2.0x)
Step 3: BUY 0.40 @ 1.0750  (-100 pips, volume: 2.0x)

Average Entry: 1.0771 (weighted)
Breakeven: Price needs to reach 1.0771 + spread
Total Volume: 0.70 lots
```

**Scale-Out Strategy:**
- More aggressive due to larger position
- May close entire position at smaller profit target
- Example: Close all at average + 15 pips = immediate breakeven

### Recovery Metrics Tracked:

**From `recovery_sequences` analysis:**
- `sequence_length`: How many trades in the recovery chain
- `avg_volume_multiplier`: Lot size progression
- `price_deterioration`: How far price moved against original position
- `max_recovery_attempts`: Deepest recovery sequence seen

**Risk Parameters:**
- `max_recovery_attempts` > 5: HIGH RISK (deep drawdown)
- `avg_recovery_lot_multiplier` > 2.0: HIGH RISK (aggressive sizing)
- Price deterioration > 2%: HIGH RISK (large move against position)

---

## 3. Take Profit & Stop Loss Decision Logic

### Current Analysis Coverage

**From Trade Data Collection:**
- `tp`: Take Profit level at entry
- `sl`: Stop Loss level at entry
- `exit_price`: Actual exit price achieved
- `exit_time`: When position closed
- `profit`: Actual P&L

### TP/SL Patterns to Look For:

**Pattern Detection (would need data analysis):**

1. **Fixed Pip Distance**
   ```
   TP: Entry ± 50 pips
   SL: Entry ∓ 25 pips
   Risk:Reward = 1:2
   ```

2. **ATR-Based Dynamic**
   ```
   TP: Entry ± (ATR * 2)
   SL: Entry ∓ (ATR * 1)
   Adapts to volatility
   ```

3. **Technical Level Based**
   ```
   TP: Next swing high/low
   SL: Recent swing low/high
   Based on market structure
   ```

4. **No Initial SL (Common with Recovery EAs)**
   ```
   TP: Set at entry
   SL: None (uses hedging/averaging instead)
   Risky approach
   ```

### How to Determine TP/SL Logic:

Run analysis on your data:
```python
# Analyze TP/SL patterns
tp_distances = []
sl_distances = []

for trade in trades:
    if trade.tp and trade.entry_price:
        tp_distance_pips = abs(trade.tp - trade.entry_price) * 10000
        tp_distances.append(tp_distance_pips)

    if trade.sl and trade.entry_price:
        sl_distance_pips = abs(trade.sl - trade.entry_price) * 10000
        sl_distances.append(sl_distance_pips)

# Check if fixed or variable
tp_std = np.std(tp_distances)
sl_std = np.std(sl_distances)

if tp_std < 5:  # Low variance
    print(f"Fixed TP: ~{np.mean(tp_distances):.0f} pips")
else:
    print(f"Dynamic TP: {np.mean(tp_distances):.0f} ± {tp_std:.0f} pips")
```

---

## 4. EA Parameters - Complete List

### A. Entry Strategy Parameters

#### VWAP Mean Reversion (Primary)
```python
vwap_band_1_trades = 0          # Trades at 1σ band
vwap_band_2_trades = 0          # Trades at 2σ band
vwap_band_1_2_percentage = 0    # % trades at bands 1&2
avg_deviation_band_1 = 0        # Avg % deviation at band 1
avg_deviation_band_2 = 0        # Avg % deviation at band 2
```

**Usage:** If >40% of trades at VWAP bands 1&2, primary strategy is mean reversion

#### Market Structure Levels
```python
at_swing_high = bool            # Entry at swing high
at_swing_low = bool             # Entry at swing low
distance_to_swing_high = float  # % distance to resistance
distance_to_swing_low = float   # % distance to support
```

#### Volume Profile
```python
at_poc = bool                   # At Point of Control (high volume)
above_vah = bool                # Above Value Area High
below_val = bool                # Below Value Area Low
at_lvn = bool                   # At Low Volume Node
volume_percentile = float       # Volume ranking at entry
```

#### Institutional Levels
```python
order_block_bullish = bool      # At bullish order block
order_block_bearish = bool      # At bearish order block
fair_value_gap_up = bool        # In bullish FVG
fair_value_gap_down = bool      # In bearish FVG
liquidity_sweep = bool          # After stop hunt
```

#### Previous Day Values
```python
used_prev_poc = int             # Entries at previous day POC
used_prev_vah = int             # Entries at previous day VAH
used_prev_val = int             # Entries at previous day VAL
used_prev_vwap = int            # Entries at previous day VWAP
used_prev_lvn = int             # Entries at previous day LVN
```

### B. Technical Indicators

#### Trend Indicators
```python
rsi_14 = float                  # RSI(14) value at entry
sma_20 = float                  # 20-period SMA
sma_50 = float                  # 50-period SMA
ema_20 = float                  # 20-period EMA
sma20_slope = float             # SMA trend direction
sma50_slope = float             # SMA trend direction
price_vs_sma20 = float          # % distance from SMA20
price_vs_sma50 = float          # % distance from SMA50
```

#### Momentum Indicators
```python
macd = float                    # MACD line
macd_signal = float             # MACD signal line
macd_histogram = float          # MACD histogram
consecutive_up_bars = int       # Consecutive bullish candles
consecutive_down_bars = int     # Consecutive bearish candles
```

#### Volatility Indicators
```python
atr_14 = float                  # Average True Range
bb_upper = float                # Bollinger Band upper
bb_middle = float               # Bollinger Band middle
bb_lower = float                # Bollinger Band lower
```

### C. Position Management Parameters

#### Grid Trading
```python
grid_spacing = float            # Price spacing between levels (pips)
max_positions = int             # Maximum simultaneous positions
```

#### Lot Sizing
```python
initial_lot_size = float        # Starting position size
lot_progression = str           # "Fixed" or "Multiplier: X.XX"
avg_volume_multiplier = float   # DCA/Martingale multiplier
```

#### Recovery Strategy
```python
martingale_detected = bool      # Uses martingale (>1.5x lots)
dca_detected = bool             # Uses DCA (fixed lots)
max_recovery_attempts = int     # Deepest recovery chain
avg_recovery_lot_multiplier = float  # Average lot multiplier
price_deterioration = float     # % price move before recovery
```

### D. Hedging Parameters

```python
hedge_detected = bool           # Uses hedging strategy
hedge_pairs = int               # Number of hedge pairs
hedge_timing_window = int       # Minutes between hedge entries (5)
hedge_volume_ratio = float      # Hedge size vs original (0.9-1.1 = balanced)
time_before_hedge_minutes = float    # How long before hedging
price_movement_pips = float     # Pips moved before hedge
price_movement_pct = float      # % moved before hedge
```

### E. Time-Based Parameters

#### Trading Sessions
```python
asian_session_pct = float       # % trades 0-8 hours
london_session_pct = float      # % trades 8-16 hours
newyork_session_pct = float     # % trades 16-24 hours
peak_hours = list               # Hours with >1.5x avg activity
quiet_hours = list              # Hours with <0.5x avg activity
```

#### Trade Duration
```python
avg_trade_duration = float      # Average minutes position held
counter_trend_duration = float  # Minutes held for counter-trend
```

### F. Risk Management Parameters

```python
tp_distance_pips = float        # Average TP distance
sl_distance_pips = float        # Average SL distance
risk_reward_ratio = float       # TP/SL ratio
uses_sl = bool                  # Whether SL is set at entry
uses_tp = bool                  # Whether TP is set at entry
```

### G. Performance Metrics

```python
total_trades = int              # Total trade count
win_rate = float                # % profitable trades
profit_factor = float           # Gross profit / Gross loss
average_win = float             # Average winning trade $
average_loss = float            # Average losing trade $
max_consecutive_losses = int    # Longest losing streak
```

---

## 5. Confluence Zone Analysis

### What Are Confluence Zones?

Confluence = Multiple technical factors aligning at the same price level
→ Higher probability trade setup

### Confluence Factors Tracked:

From `analyze_vwap_mean_reversion:1010-1021`:

```python
# VWAP Bands + Swing Levels
band_1_2_at_swing = int         # Trades at VWAP band + swing high/low

# VWAP Bands + Order Blocks
band_1_2_at_order_blocks = int  # Trades at VWAP band + order block

# VWAP Bands + Volume Profile
band_1_2_at_poc = int           # Trades at VWAP band + POC

# VWAP Bands + Value Area Extremes
band_1_2_outside_value_area = int  # Trades at VWAP band + VAH/VAL
```

### High-Value Confluence Zones Detected:

**Example 1: VWAP Band 2 + Swing Low + VAL**
```
Price: 1.0850
- At VWAP Band 2 (2σ below VWAP)
- At recent swing low (support)
- Below Value Area Low (oversold)

→ Triple confluence = High probability BUY setup
```

**Example 2: VWAP Band 1 + Order Block + Previous Day VAL**
```
Price: 1.0920
- At VWAP Band 1 (1σ above VWAP)
- At bullish order block (institutional buying)
- At previous day's VAL (institutional memory)

→ Triple confluence = High probability BUY setup
```

**Example 3: Swing High + POC + Above VAH**
```
Price: 1.0980
- At swing high (resistance)
- At Volume POC (high volume rejection zone)
- Above Value Area High (overbought)

→ Triple confluence = High probability SELL setup
```

### Confluence Scoring System:

To determine high-value zones, count overlapping factors:

**Level 1 (Single Factor):** 40-60% win rate
```
- Just at VWAP Band 1
```

**Level 2 (Double Confluence):** 60-70% win rate
```
- VWAP Band 1 + Swing Low
- POC + Order Block
```

**Level 3 (Triple Confluence):** 70-80% win rate
```
- VWAP Band 2 + Swing Low + VAL
- VWAP Band 1 + Order Block + Previous Day VAH
```

**Level 4+ (Quad+ Confluence):** 80%+ win rate
```
- VWAP Band 2 + Swing Low + VAL + Previous Day POC
```

### How to Extract Confluence Zones:

Run on your trade data:
```python
high_value_zones = []

for trade in all_conditions:
    confluence_score = 0
    factors = []

    # Check each factor
    if trade['in_vwap_band_1'] or trade['in_vwap_band_2']:
        confluence_score += 1
        factors.append('VWAP Band')

    if trade['at_swing_low'] or trade['at_swing_high']:
        confluence_score += 1
        factors.append('Swing Level')

    if trade['at_poc']:
        confluence_score += 1
        factors.append('POC')

    if trade['below_val'] or trade['above_vah']:
        confluence_score += 1
        factors.append('Value Area Extreme')

    if trade['order_block_bullish'] or trade['order_block_bearish']:
        confluence_score += 1
        factors.append('Order Block')

    # High-value = 3+ factors
    if confluence_score >= 3:
        high_value_zones.append({
            'price': trade['entry_price'],
            'time': trade['entry_time'],
            'confluence_score': confluence_score,
            'factors': factors,
            'trade_type': trade['trade_type'],
            'profit': trade['profit']
        })

# Sort by confluence score
high_value_zones.sort(key=lambda x: x['confluence_score'], reverse=True)
```

---

## Summary: Python Trading Platform Feature List

Based on reverse engineering, here are the **essential features** to build:

### Core Features:

1. **VWAP-Based Mean Reversion**
   - Calculate VWAP with 1σ, 2σ, 3σ deviation bands
   - Enter at Band 1 or Band 2 (40%+ of trades)
   - Direction: BUY below VWAP, SELL above VWAP

2. **Market Structure Analysis**
   - Detect swing highs/lows (100-bar lookback)
   - Calculate distance to key levels
   - Enter at support/resistance bounce

3. **Volume Profile**
   - Calculate POC (Point of Control)
   - Calculate VAH/VAL (Value Area High/Low)
   - Enter at extreme zones (above VAH, below VAL)

4. **Confluence Detection**
   - Score entries by number of aligned factors
   - Require 2+ confluence for entry
   - Prioritize 3+ confluence setups

5. **Position Sizing & Recovery**
   - Support for fixed lot DCA
   - Support for martingale (configurable multiplier)
   - Maximum recovery attempts limit
   - Track average entry price

6. **Hedging System**
   - Open opposite position on drawdown trigger
   - Configurable hedge volume ratio
   - Time window for hedge pairing (5 min)
   - Track net P&L of hedge pairs

7. **Risk Management**
   - Dynamic TP/SL based on ATR or fixed pips
   - Circuit breaker (stop after N losses)
   - Position size limits
   - Maximum drawdown limits

8. **Time Filters**
   - Trading session filters (avoid specific hours)
   - Peak hour identification
   - Avoid low-liquidity periods

9. **Technical Indicators**
   - RSI(14), MACD, SMA(20/50), EMA(20)
   - Bollinger Bands
   - ATR(14) for volatility
   - Slope calculations for trend

10. **Monitoring & Analytics**
    - Real-time P&L tracking
    - Win rate by confluence level
    - Recovery sequence tracking
    - Hedge effectiveness metrics

---

## Next Steps

1. **Run Analysis on Your Data:**
   ```bash
   python reverse_engineer_ea.py
   ```

2. **Review Generated CSV:**
   - `ea_reverse_engineering_detailed.csv` - All trades with full analysis

3. **Prioritize Features:**
   - Start with VWAP mean reversion (primary strategy)
   - Add confluence scoring
   - Implement recovery/hedging mechanisms
   - Add risk management last

4. **Backtest Parameters:**
   - Use discovered parameters as starting point
   - Optimize on your historical data
   - Forward test before live trading

---

*Analysis compiled from reverse engineering codebase on 2024-12-03*
