# Trading Strategy Time Windows Summary

## Overview

The bot now runs **TWO strategies** with optimized time windows based on historical analysis:
- **Mean Reversion** (79.3% win rate at Value Area)
- **Breakout** (complementary trending strategy)

---

## Mean Reversion Strategy

### Trading Hours (UTC)
- **05:00** - 100% win rate (17 trades)
- **06:00** - 86% win rate (7 trades)
- **07:00** - 93% win rate (15 trades)
- **09:00** - 80% win rate (30 trades)
- **12:00** - 100% win rate (4 trades)

### Trading Days
- **Monday** ✅ (included per user request)
- **Tuesday** ✅ (73% win rate)
- **Wednesday** ✅ (70% win rate)
- **Thursday** ✅ (69% win rate)
- ❌ Friday (64% win rate - excluded)

### Trading Sessions
- **Tokyo** (00:00-09:00 UTC) - 74% win rate
- **London** (08:00-17:00 UTC) - 68% win rate
- ❌ New York (13:00-22:00 UTC) - 53% win rate - excluded

### Entry Conditions
- Price at VWAP ±1σ or ±2σ bands
- At POC (Point of Control) - high volume level
- At Value Area (VAH/VAL) - 70% volume boundary
- Minimum 4 confluence factors
- ADX < 25 (ranging market)
- Low/medium volatility periods

### Best Entry Type
**Value Area (VAH/VAL):**
- 79.3% win rate
- $6.43 average profit
- 4.7 hours average duration

---

## Breakout Strategy

### Trading Hours (UTC)
- **03:00** - 70% win rate (10 trades, high volatility)
- **14:00-16:00** - London/NY overlap (highest volatility)

### Trading Days
- **Monday** ✅ (week open breakouts)
- **Tuesday** ✅ (62% win rate, high volatility)
- ❌ Wednesday (excluded)
- ❌ Thursday (excluded)
- **Friday** ✅ (trend exhaustion plays)

### Trading Sessions
- **Tokyo** (00:00-09:00 UTC) - For 03:00 hour only
- **London** (08:00-17:00 UTC) - High volatility
- **New York** (13:00-22:00 UTC) - London/NY overlap

### Entry Conditions
- Price breaks range high/low (20-bar range minimum)
- Volume spike (1.5x average volume)
- High volatility (ATR > 1.2x median)
- RSI > 60 (buy) or RSI < 40 (sell)
- Strong momentum (MACD histogram alignment)
- NOT at VWAP bands (trending, not reverting)

### Breakout Types Implemented
1. **Range Breakout** - Price breaks consolidation range
2. **LVN Breakout** - Price breaks through Low Volume Nodes (fast moves)
3. **Weekly Level Breakout** - Previous week high/low breaks

### Position Sizing
- **50% smaller lots** than mean reversion (lower win rate, higher R:R)
- Risk: 1% per trade maximum
- Tight stops (20% of range back from breakout level)

### Profit Targets
- **Range Projection:** Entry + range size
- **ATR Multiple:** Entry + 2x ATR
- **LVN Target:** Next Low Volume Node (expect fast move)

---

## Strategy Separation

### No Overlap Hours
The strategies have **ZERO overlapping hours** to prevent conflicts:

**Mean Reversion Hours:** 05:00, 06:00, 07:00, 09:00, 12:00
**Breakout Hours:** 03:00, 14:00, 15:00, 16:00

### Hourly Schedule (UTC)

| Hour | Strategy | Session | Why |
|------|----------|---------|-----|
| 03:00 | Breakout | Tokyo | High ATR, 70% win |
| 05:00 | Mean Reversion | Tokyo | 100% win rate |
| 06:00 | Mean Reversion | Tokyo | 86% win rate |
| 07:00 | Mean Reversion | Tokyo | 93% win rate |
| 09:00 | Mean Reversion | London | 80% win rate |
| 12:00 | Mean Reversion | London | 100% win rate |
| 14:00 | Breakout | London/NY | High volatility overlap |
| 15:00 | Breakout | London/NY | High volatility overlap |
| 16:00 | Breakout | London/NY | High volatility overlap |

### Weekly Schedule

| Day | MR Hours | BO Hours | Total Hours |
|-----|----------|----------|-------------|
| Monday | 5,6,7,9,12 | 3,14,15,16 | 9 hours |
| Tuesday | 5,6,7,9,12 | 3,14,15,16 | 9 hours |
| Wednesday | 5,6,7,9,12 | - | 5 hours |
| Thursday | 5,6,7,9,12 | - | 5 hours |
| Friday | - | 3,14,15,16 | 4 hours |
| Saturday | - | - | 0 hours |
| Sunday | - | - | 0 hours |

---

## Configuration Files

### 1. Strategy Configuration
**File:** `trading_bot/config/strategy_config.py`

**Key Parameters Added:**
```python
# Time filter control
ENABLE_TIME_FILTERS = True

# Mean Reversion windows
MEAN_REVERSION_HOURS = [5, 6, 7, 9, 12]
MEAN_REVERSION_DAYS = [0, 1, 2, 3]  # Mon-Thu
MEAN_REVERSION_SESSIONS = ['tokyo', 'london']

# Breakout windows
BREAKOUT_HOURS = [3, 14, 15, 16]
BREAKOUT_DAYS = [0, 1, 4]  # Mon, Tue, Fri
BREAKOUT_SESSIONS = ['tokyo', 'london', 'new_york']

# Breakout strategy
BREAKOUT_ENABLED = True
BREAKOUT_VOLUME_MULTIPLIER = 1.5
BREAKOUT_ATR_MULTIPLIER = 1.2
BREAKOUT_LOT_SIZE_MULTIPLIER = 0.5
```

### 2. Breakout Strategy Module
**File:** `trading_bot/strategies/breakout_strategy.py`

**Main Class:** `BreakoutStrategy`

**Methods:**
- `detect_range_breakout()` - Consolidation breakouts
- `detect_lvn_breakout()` - Low Volume Node breakouts
- `detect_weekly_level_breakout()` - Weekly high/low breaks
- `check_breakout_signal()` - Main signal checker

### 3. Time Filter Module
**File:** `trading_bot/strategies/time_filters.py`

**Main Class:** `TimeFilter`

**Methods:**
- `can_trade_mean_reversion()` - Check if MR can trade
- `can_trade_breakout()` - Check if BO can trade
- `get_active_strategy()` - Determine active strategy
- `get_time_status()` - Full status report

---

## Testing

### Test Time Filters
```bash
python -m trading_bot.strategies.time_filters
```

**Expected Output:**
- Trading schedule for both strategies
- Hourly breakdown
- Test scenario results

### Validate Configuration
```python
from trading_bot.strategies.breakout_strategy import validate_breakout_time_filters

validation = validate_breakout_time_filters()
print(f"Valid: {validation['valid']}")  # Should be True
print(f"Overlap: {validation['overlap_hours']}")  # Should be []
```

---

## How It Works

### 1. Bot Start
1. Load `strategy_config.py` with time windows
2. Initialize `TimeFilter` with MR and BO schedules
3. Initialize `BreakoutStrategy` with entry logic

### 2. Each Tick/Bar
```python
# Check current time
current_time = datetime.now(timezone.utc)
active_strategy = time_filter.get_active_strategy(current_time)

if active_strategy == 'mean_reversion':
    # Check VWAP bands, POC, Value Area
    # Use confluence scoring
    # Enter at extremes, exit at mean

elif active_strategy == 'breakout':
    # Check range breaks, LVN levels, weekly levels
    # Require volume spike + momentum
    # Enter on break, target next resistance

else:
    # Outside trading hours - no new entries
    # Only manage existing positions
```

### 3. Position Management
- **Mean Reversion:** Uses grid/hedge/DCA recovery
- **Breakout:** Uses tight stops, no recovery (cut losses fast)

---

## Expected Results

### Mean Reversion (Primary Strategy)
- **Volume:** ~70-80% of all trades
- **Win Rate:** 70-80%
- **Avg Profit:** $5-7 per trade
- **Risk:Reward:** 1:1 to 1:1.5

### Breakout (Secondary Strategy)
- **Volume:** ~20-30% of all trades
- **Win Rate:** 50-60%
- **Avg Profit:** $10-15 per trade (higher R:R)
- **Risk:Reward:** 1:2 to 1:3

### Combined Performance
- **Overall Win Rate:** 65-75%
- **Diversification:** MR for ranging, BO for trending
- **Complementary:** Strategies don't compete for same setups

---

## Disabling Time Filters

If you want to trade all hours (not recommended):

```python
# In trading_bot/config/strategy_config.py
ENABLE_TIME_FILTERS = False
```

Or disable breakout strategy entirely:

```python
BREAKOUT_ENABLED = False
```

---

## Analysis Files

### Mean Reversion Analysis
- `analyze_mean_reversion_timing.py` - Analysis script
- `mean_reversion_timing_analysis.json` - Full results
- `mean_reversion_hourly_analysis.csv` - CSV export

### Breakout Analysis
- `analyze_breakout_timing.py` - Analysis script
- `breakout_timing_analysis.json` - Full results
- `breakout_hourly_analysis.csv` - CSV export

### Strategy Guides
- `BREAKOUT_STRATEGY_EXPLAINED.md` - Complete breakout guide
- `MULTI_TIMEFRAME_ANALYSIS.md` - Volume profile analysis
- `GRID_AND_HEDGE_STRATEGY_CONFIRMED.md` - Recovery strategy

---

## Next Steps

### 1. Backtest Combined Strategy
Test both strategies together on historical data to validate:
- Time windows don't conflict
- Combined win rate meets expectations
- Position sizing works correctly

### 2. Paper Trade
Run on demo account for 1-2 weeks:
- Monitor which strategy triggers more
- Track win rates by strategy type
- Adjust time windows if needed

### 3. Optimize
After collecting data:
- Refine time windows if certain hours underperform
- Adjust breakout parameters (volume multiplier, ATR threshold)
- Fine-tune position sizing

---

## Support

### Checking Current Status
```python
from trading_bot.strategies.time_filters import TimeFilter
from datetime import datetime

filter = TimeFilter()
status = filter.get_time_status(datetime.utcnow())

print(f"Active Strategy: {status['active_strategy']}")
print(f"Can trade MR: {status['can_trade_mean_reversion']}")
print(f"Can trade BO: {status['can_trade_breakout']}")
```

### View Full Schedule
```python
filter.print_schedule()
```

---

**Created:** 2025-12-23
**Analysis Period:** Nov 13-19, 2025 (413 trades)
**Strategies:** Mean Reversion + Breakout
**Time Filters:** Active ✅
**Breakout Enabled:** True ✅
