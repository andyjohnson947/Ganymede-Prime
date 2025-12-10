# EA Trading Flow Analysis

## Why Are 196 Out of 201 Trades Being Filtered?

### Root Cause: ML Model Poor Prediction Accuracy

The backtest shows **196 trades filtered out of 201** (97.5% filtered). Here's why:

### The Problem Flow:

```
Historical EA Trade → Get market data at that time → ML Model predicts → Only 5/193 = "should_trade: True"
```

**src/ea_mining/strategy_enhancer.py:248**
```python
# For each historical EA trade...
ea_pred = self.learner.predict(entry_data)  # Ask ML: "Would EA trade here?"
```

**src/ea_mining/ea_learner.py:346**
```python
# ML model says "trade" only if probability > 50%
predictions['should_trade'] = bool(should_trade_proba[1] > 0.5)
```

**src/ea_mining/strategy_enhancer.py:254**
```python
# Only keep trade if ML says "should_trade"
if enhanced_signal['enhanced_signal']['should_trade']:
    enhanced_trades.append(modified_trade)  # ← Only happens 5 times out of 193!
```

### Why Is ML Model Accuracy So Low?

Even though the EA **actually** traded 193 times, the ML model only predicts "should trade" for 5 of them (2.6% recall).

**Possible Reasons:**

1. **Feature Timing Mismatch**
   - Training data enriches features BEFORE matching to trade times
   - Backtest enriches data differently
   - Indicators might not align exactly to the same bar

2. **Model Overfitting or Underfitting**
   - 193 positive samples (EA trades)
   - ~200+ negative samples (random non-trade bars sampled every 10th bar)
   - Model might not generalize well

3. **Threshold Too High**
   - Requiring >50% probability is strict
   - ML model might have lower confidence even for valid trades

4. **Data Leakage or Lookahead Bias**
   - Training might see future data that backtest doesn't have

---

## Complete Trade Entry Process

### Step 1: EA Monitoring (Historical Data Collection)

**File: src/ea_mining/ea_monitor.py**

```python
class EATrade:
    ticket: int          # MT5 position ticket
    symbol: str          # EURUSD+, etc.
    trade_type: str      # 'buy' or 'sell'
    entry_time: datetime
    entry_price: float
    volume: float
    magic_number: int    # EA identifier
    comment: str         # EA comment field
```

**How trades are collected:**
- Fetches ALL historical deals from MT5: `mt5.history_deals_get()`
- Filters by magic_number if specified (identifies specific EA)
- Groups deals into completed trades (entry + exit pairs)
- Stores in `self.known_trades` dictionary keyed by ticket number

**No Grid/Hedge Detection:** Each position is tracked individually by ticket. If EA opens multiple positions (grid/hedge), each gets its own ticket and is tracked separately.

---

### Step 2: ML Training Data Preparation

**File: src/ea_mining/ea_learner.py:52-169**

**Positive Samples (ea_traded=1):**
```python
# For each EA trade at entry_time:
entry_features = df.iloc[entry_idx].to_dict()  # Get all 114 features at that bar
entry_features['ea_traded'] = 1               # Label: EA DID trade here
```

**Negative Samples (ea_traded=0):**
```python
# Sample random bars where EA didn't trade (every 10th bar):
for idx in range(100, len(df), 10):
    if not_a_trade_time:
        non_trade_features = df.iloc[idx].to_dict()
        non_trade_features['ea_traded'] = 0  # Label: EA did NOT trade
```

**Result:**
- ~193 positive samples (actual EA trades)
- ~200+ negative samples (random non-trade bars)
- Model learns to distinguish "EA trades here" vs "EA doesn't trade here"

---

### Step 3: ML Model Training

**File: src/ea_mining/ea_learner.py:209-285**

**Entry Model (When to Trade):**
```python
# Features: 114 engineered indicators (ROC, slopes, volume, support/resistance)
# Target: ea_traded (1 = EA traded, 0 = EA didn't trade)
# Model: RandomForestClassifier

X = entry_df[feature_cols]  # All numeric features
y = entry_df['ea_traded']   # Binary: trade or not

entry_model.fit(X_train, y_train)
```

**Direction Model (Buy vs Sell):**
```python
# Features: Same 114 indicators
# Target: direction (1 = buy, 0 = sell)
# Only trained on trades where EA actually entered

X = direction_df[feature_cols]
y = direction_df['direction']  # 1=buy, 0=sell

direction_model.fit(X_train, y_train)
```

---

### Step 4: Prediction (What Would EA Do?)

**File: src/ea_mining/ea_learner.py:322-361**

```python
def predict(current_data: pd.DataFrame):
    latest = current_data.iloc[[-1]]  # Get most recent bar with all 114 features

    # Entry Model: Should EA trade?
    X_entry = latest[entry_feature_names]
    should_trade_proba = entry_model.predict_proba(X_entry)[0]

    should_trade = should_trade_proba[1] > 0.5  # ← CRITICAL: Only True if >50% confidence
    trade_probability = should_trade_proba[1]

    # Direction Model: Buy or sell?
    if should_trade:
        X_direction = latest[direction_feature_names]
        direction_proba = direction_model.predict_proba(X_direction)[0]
        direction = 'buy' if direction_proba[1] > 0.5 else 'sell'

    return {
        'should_trade': should_trade,      # ← This is False for 188/193 historical trades!
        'trade_probability': trade_probability,
        'direction': direction
    }
```

---

### Step 5: Enhanced Signal Generation

**File: src/ea_mining/strategy_enhancer.py:122-207**

```python
def generate_enhanced_signal(current_data, ea_prediction):
    # Start with ML model's decision
    should_trade = ea_prediction.get('should_trade', False)  # ← Often False!

    # Apply filters ONLY if should_trade is True
    if should_trade:
        # Time filter: Avoid bad hours
        for filter_rule in filters:
            if current_hour == avoid_hour:
                should_trade = False
                break

        # Confirmation filter: Check indicators aligned
        # (Currently not implemented - just placeholder)

    # Risk management adjustments
    stop_loss_multiplier = 0.75   # Tighten SL by 25%
    take_profit_multiplier = 1.5  # Widen TP by 50%

    return {
        'enhanced_signal': {
            'should_trade': should_trade,  # ← False for 188/193 trades
            'direction': direction,
            'confidence': confidence,
            'stop_loss_multiplier': 0.75,
            'take_profit_multiplier': 1.5
        }
    }
```

---

### Step 6: Backtest

**File: src/ea_mining/strategy_enhancer.py:209-303**

```python
def backtest_enhancements(historical_data):
    enhanced_trades = []

    # For each historical EA trade (193 trades):
    for ea_trade in ea_trades:
        entry_time = ea_trade['entry_time']
        entry_data = df.iloc[:entry_idx + 1]  # All data up to entry

        # Ask ML: "Would EA trade here?"
        ea_pred = self.learner.predict(entry_data)  # ← Returns should_trade=False for 188/193

        # Generate enhanced signal
        enhanced_signal = generate_enhanced_signal(entry_data, ea_pred)

        # Only keep if enhanced signal says trade
        if enhanced_signal['enhanced_signal']['should_trade']:  # ← Only True for 5/193!
            enhanced_trades.append(modified_trade)

    # Result: 5 trades vs 193 original trades
    trades_filtered = 193 - 5 = 188
```

---

## Grid & Hedge Position Handling

### Current Implementation: **None**

**Each position is tracked individually:**
- Grid positions: Multiple separate tickets, all tracked individually
- Hedge positions: Opposite direction trades tracked separately
- Martingale/averaging: Each add-on is a new ticket

**No correlation or grouping logic:**
- Trades are not grouped by strategy type
- No detection of grid patterns
- No detection of hedge pairs
- No averaging detection

**Example:**
```
EA opens grid on EURUSD:
- Ticket 12345: Buy 0.01 @ 1.0850
- Ticket 12346: Buy 0.01 @ 1.0800
- Ticket 12347: Buy 0.01 @ 1.0750

System sees: 3 independent trades
System doesn't know: They're related grid positions
```

### Implications:

1. **ML training treats grid trades as independent**
   - Each grid level is a separate "EA traded" sample
   - Model doesn't learn grid spacing or correlation

2. **Backtest doesn't replicate grid behavior**
   - If first grid level is filtered, subsequent levels aren't opened
   - Destroys grid recovery logic

3. **Statistics may be misleading**
   - Win rate counts each grid position separately
   - Total profit sums all positions (correct for final P&L, but not for strategy understanding)

---

## Summary: The Fundamental Issues

### 1. **ML Model Can't Reproduce EA Decisions**
- Only predicts 5/193 trades correctly (2.6% recall)
- Makes enhanced strategy ultra-conservative
- Defeats purpose of learning EA behavior

### 2. **Backtest Logic Is Flawed**
```python
# Current (wrong):
if ML_model_says_trade AND filters_pass:
    take_trade

# Should be:
if EA_actually_traded:  # We KNOW EA traded
    if filters_allow:
        take_trade  # Apply enhancements to EA's decisions
```

### 3. **No Grid/Hedge Awareness**
- Treats all positions independently
- Can't learn multi-position strategies
- Backtest won't replicate grid recovery

---

## Recommendations

### Option 1: Fix Backtest Logic (Simple)
```python
# Start with EA's actual decision, not ML prediction
for ea_trade in ea_trades:
    # We KNOW EA traded here
    ea_pred = {'should_trade': True, 'direction': ea_trade['type']}

    # Apply ONLY enhancement filters
    enhanced_signal = generate_enhanced_signal(entry_data, ea_pred)

    if enhanced_signal['enhanced_signal']['should_trade']:
        enhanced_trades.append(modified_trade)
```

### Option 2: Improve ML Model
- Lower threshold (e.g., >0.3 instead of >0.5)
- More training data (more negative samples)
- Feature engineering review
- Cross-validation to check generalization

### Option 3: Add Grid/Hedge Detection
- Group trades by magic_number + comment patterns
- Detect grid spacing (equal price intervals)
- Detect hedge pairs (opposite directions, similar volumes)
- Track strategy families, not individual trades

---

## Current Trade Flow Diagram

```
MT5 Historical Deals
       ↓
EA Monitor: Collect trades → 193 trades
       ↓
Feature Engineering → Add 114 indicators
       ↓
ML Training:
  Positive: 193 EA trades (ea_traded=1)
  Negative: ~200 random bars (ea_traded=0)
       ↓
RandomForest Models:
  Entry Model: 114 features → should_trade
  Direction Model: 114 features → buy/sell
       ↓
Backtest:
  For each historical trade:
    ML predict() → should_trade=True only 2.6% of time
    Enhanced signal → inherits False
    Result → 188/193 filtered out
       ↓
Final Result:
  Original EA: 193 trades, 68.9% win, $1093 profit
  Enhanced: 5 trades, 60% win, $12 profit ❌
```

**The ML bottleneck is killing performance.**
