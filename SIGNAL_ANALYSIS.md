# 🔍 Signal Detection Analysis - Why No Signals?

## Overview
Your bot uses a **highly selective** mean-reversion strategy with strict confluence requirements. This analysis explains why signals may be rare and what conditions must align for a trade.

## Signal Requirements (ALL must be met)

### 1. ✅ Confluence Score ≥ 4
- Your bot requires at least **4 points of confluence** before entering a trade
- This is intentionally strict to achieve the 64.3% win rate
- Confluence points come from:

#### VWAP Factors (Weight: 1 point each)
- **VWAP Band 1** (±1σ): Price must touch or exceed the first standard deviation band
- **VWAP Band 2** (±2σ): Price must touch or exceed the second standard deviation band

#### Volume Profile Factors (Weight: 1 point each)
- **POC** (Point of Control): Price at highest volume level
- **Above VAH** (Value Area High): Price at resistance zone
- **Below VAL** (Value Area Low): Price at support zone
- **LVN** (Low Volume Node): Price at low-liquidity zone (breakout area)
- **Swing High/Low**: Price at previous swing points

#### HTF Factors (Weight: 2-3 points each - MOST IMPORTANT)
- **Daily POC** (2 pts): Price at yesterday's point of control
- **Daily VAH/VAL** (2 pts): Price at yesterday's value area
- **Daily HVN** (2 pts): Price at daily high volume node
- **Weekly POC** (3 pts): Price at weekly point of control
- **Weekly HVN** (3 pts): Price at weekly high volume node
- **Prev Week Swing High/Low** (2 pts): Price at last week's swing points

### 2. ✅ Time Window Filter
**Mean Reversion** can only trade during these GMT hours:
- **5, 6, 7, 9, 12** (Tokyo, early London)

**Breakout** can only trade during these GMT hours:
- **3, 14, 15, 16** (Tokyo open, London/NY overlap)

**Hour 19 GMT**: ❌ NOT ALLOWED FOR EITHER STRATEGY

### 3. ✅ Trading Calendar
Bot will NOT trade during:
- ❌ Bank holidays (UK/US)
- ❌ Weekends (Saturday/Sunday)
- ❌ Friday afternoons (15:00 GMT onwards)

### 4. ✅ Trend Filter (ADX)
If enabled, bot checks:
- **ADX > 40**: ❌ NO TRADE (too strong trend, mean reversion won't work)
- **ADX 25-40**: ⚠️ Caution - checks candle alignment
- **ADX < 25**: ✅ OK to trade (ranging/weak trend)

### 5. ✅ Portfolio Window
Instrument must be in its trading window:
- **EURUSD/GBPUSD**: 00:00-23:59 GMT (all day, time filters apply)

---

## Why Signals Are Rare

### Reason #1: Price Must Reach Extremes
The bot is looking for **mean reversion** opportunities. This means:
- Price must move **away from VWAP** to the ±1σ or ±2σ bands
- Price must hit **institutional levels** (POC, VAH, VAL)
- If price is ranging in the middle of VWAP bands: **NO SIGNAL**

**Example:**
```
EURUSD trading at 1.0500, VWAP at 1.0495
VWAP +1σ band at 1.0520
VWAP -1σ band at 1.0470

Current position: Price is 5 pips above VWAP
Status: ❌ NOT FAR ENOUGH - no signal
Needs: Price to reach 1.0520 (upper band) or 1.0470 (lower band)
```

### Reason #2: Multiple Factors Must Align
Getting 4+ confluence points requires:
- Price at VWAP band (1 pt) +
- Price at POC or VAH/VAL (1 pt) +
- Price at HTF level like Daily POC (2 pts) = **4 points total**

OR:
- Price at VWAP ±2σ band (1 pt) +
- Price at swing high/low (1 pt) +
- Price at Weekly HVN (3 pts) = **5 points total**

If price hits a VWAP band but ISN'T at any other institutional level: **NO SIGNAL**

### Reason #3: Time Restrictions
Even with 4+ confluence, if current hour is NOT in the allowed list:
- Hour 19 GMT: ❌ Not in MR hours (5,6,7,9,12) or BO hours (3,14,15,16)
- Hour 22 GMT: ❌ Not in MR or BO hours
- Hour 1 GMT: ❌ Not in MR or BO hours

**Only 9 hours per day are tradeable** (5 for MR, 4 for BO with some overlap)

### Reason #4: Strong Trends Block Trades
If market is trending strongly (ADX > 40):
- Mean reversion is risky
- Bot will NOT trade even with perfect confluence

---

## What Changed? (User reported "was working, now garbage")

### Possible Changes That Could Affect Signals:

1. **BROKER_GMT_OFFSET Changed**
   - Was: 0 (correct)
   - User changed to: 2
   - Effect: Bot checks hour 17 when it should check hour 19
   - Result: Misses trading windows by 2 hours
   - **FIX: Set BROKER_GMT_OFFSET = 0**

2. **Time Filters Recently Added**
   - Previous version may have traded all day
   - New version restricts to specific hours
   - Effect: 9 hours/day tradeable vs 24 hours/day
   - **FIX: Use --test-mode flag to trade all day**

3. **Portfolio Windows Changed**
   - Previous: Multiple narrow windows
   - Current: 00:00-23:59 (all day)
   - Effect: Should be MORE permissive now, not less

4. **Confluence Requirements**
   - Current: MIN_CONFLUENCE_SCORE = 4
   - If previous version had lower threshold (e.g., 3): More signals
   - **Check: Was MIN_CONFLUENCE_SCORE changed?**

---

## How to Test

### Option 1: Test Mode (Trade All Day)
```bash
python main.py --login XXX --password YYY --server ZZZ --test-mode
```
- Bypasses ALL time filters
- Trades any hour of the day
- Still requires 4+ confluence
- Use this to see if TIME FILTERS are the issue

### Option 2: Run Diagnostic Script
```bash
python diagnose_signals.py
```
- Analyzes last 48 hours of market data
- Shows all signals that were detected
- Shows which signals were blocked by time filters
- Shows confluence scores for each bar
- **Use this to understand what the bot is "seeing"**

### Option 3: Lower Confluence Temporarily
Edit `config/strategy_config.py`:
```python
# Line 24
MIN_CONFLUENCE_SCORE = 3  # Was 4, lower to 3 for testing
```
- Restart bot
- Should see more signals
- **WARNING: Lower win rate expected**

---

## Expected Behavior

### From EA Analysis (428 trades):
- **Win rate**: 64.3%
- **Trade frequency**: ~413 trades over extended period (patient strategy)
- **Not a scalper**: May go hours or days without trades
- **Selective by design**: Quality over quantity

### Normal Signal Rate:
- **Good day**: 2-5 signals across EURUSD + GBPUSD
- **Slow day**: 0-1 signals (market ranging in middle of bands)
- **Active day**: 5-10 signals (high volatility, price hitting extremes)

---

## Immediate Action Items

1. **Set BROKER_GMT_OFFSET = 0** (if currently 2)
   - File: `config/strategy_config.py`, line 200
   - Restart bot after change

2. **Run diagnostic script**
   ```bash
   python diagnose_signals.py
   ```
   - This will show if ANY signals existed in last 48 hours
   - Shows if time filters blocked them

3. **Try test mode**
   ```bash
   python main.py --login XXX --password YYY --server ZZZ --test-mode
   ```
   - If signals appear in test mode → time filters are the issue
   - If no signals even in test mode → market hasn't reached confluence levels

4. **Check current market position**
   - Open MT5
   - Check EURUSD current price vs VWAP bands
   - If price is in middle of bands → bot is CORRECTLY not trading

---

## Technical Confidence Check

✅ **Bot is working correctly IF:**
- No signals because price hasn't reached VWAP ±1σ or ±2σ bands
- No signals because confluence score is 1, 2, or 3 (below threshold of 4)
- No signals because current hour is outside allowed windows

❌ **Bot has a problem IF:**
- Signals ARE detected but not being executed
- Time filters are blocking ALL signals due to wrong GMT offset
- Confluence logic is broken (diagnostic script will show this)

---

## Next Steps

1. Run `diagnose_signals.py` to get the full picture
2. Review the output to see:
   - Were ANY confluence factors detected?
   - What were the confluence scores?
   - Were signals blocked by time filters?
3. Share the output for further analysis

The bot is designed to be PATIENT and SELECTIVE. Lack of signals may be correct behavior if market conditions don't meet the strict requirements.
