# TIMEZONE CONFIGURATION GUIDE

## ⚠️ CRITICAL: SET YOUR BROKER'S TIMEZONE

The bot now includes **automatic timezone conversion** between your MT5 broker's time and GMT/UTC.

---

## WHY THIS MATTERS

Different MT5 brokers use different server timezones:
- **European brokers:** Usually GMT+2 (winter) or GMT+3 (summer)
- **US brokers:** GMT-4 (summer) or GMT-5 (winter)
- **Some brokers:** GMT+0 (UTC) year-round

**If timezone is wrong:**
- Bot trades at wrong hours
- Miss profitable setups
- Trade during low-performance windows

---

## HOW TO FIND YOUR BROKER'S TIMEZONE

### Method 1: Compare MT5 Time to GMT

1. Open https://time.is/GMT in your browser
2. Check current GMT time (e.g., 12:00)
3. Check MT5 terminal time (bottom-right corner of MT5)
4. Calculate offset: `MT5 time - GMT time`

**Example:**
```
GMT time:  12:00
MT5 time:  14:00
Offset:    +2 (GMT+2)
```

### Method 2: Check Broker Documentation

Most brokers specify their server timezone in:
- Account dashboard
- Trading platform settings
- Broker website "Trading Conditions" page

### Common Broker Timezones

| Broker Type | Timezone | Offset | Example MT5 Time when GMT is 12:00 |
|-------------|----------|--------|-----------------------------------|
| Most EU brokers | GMT+2/+3 | +2 or +3 | 14:00 or 15:00 |
| IC Markets | GMT+2/+3 | +2 or +3 | 14:00 or 15:00 |
| Pepperstone | GMT+2/+3 | +2 or +3 | 14:00 or 15:00 |
| OANDA | GMT+0 | 0 | 12:00 |
| Some US brokers | EST/EDT | -5 or -4 | 07:00 or 08:00 |

---

## CONFIGURING YOUR TIMEZONE

### Step 1: Open Configuration File

Edit: `trading_bot/config/strategy_config.py`

### Step 2: Find BROKER_GMT_OFFSET

Look for this line (around line 200):
```python
BROKER_GMT_OFFSET = 0  # SET THIS TO YOUR BROKER'S OFFSET!
```

### Step 3: Set Your Offset

Replace `0` with your broker's offset:

```python
# Example: If your broker is GMT+2
BROKER_GMT_OFFSET = 2

# Example: If your broker is GMT+3
BROKER_GMT_OFFSET = 3

# Example: If your broker is EST (GMT-5)
BROKER_GMT_OFFSET = -5

# Example: If your broker uses GMT/UTC
BROKER_GMT_OFFSET = 0
```

### Step 4: Save File

Save `strategy_config.py`

---

## TESTING YOUR CONFIGURATION

### Quick Test

Run this command:
```bash
python -m trading_bot.strategies.time_filters
```

**What to check:**
1. Look for "TIMEZONE CONVERSION TEST" section
2. Find your broker's offset (e.g., GMT+2)
3. Verify conversion is correct:
   - If MT5 shows 07:00 and you're GMT+2
   - GMT time should show 05:00
   - Should say "Can trade MR: True" (if Tuesday-Thursday)

### Example Output

```
📍 BROKER TIMEZONE: GMT+2
--------------------------------------------------------------------------------
Broker Time: 07:00
GMT Time:    05:00
Can trade MR: True
Can trade BO: False
Active Strategy: mean_reversion
```

If this matches your expectation, you're configured correctly!

---

## HOW IT WORKS

### Behind the Scenes

1. **MT5 returns time in broker timezone** (e.g., 14:00 GMT+2)
2. **Bot converts to GMT** → 14:00 - 2 hours = 12:00 GMT
3. **Bot checks if 12:00 GMT is in trading windows**:
   - Mean Reversion Hours: 05:00, 06:00, 07:00, 09:00, 12:00 GMT ✅
   - Breakout Hours: 03:00, 14:00, 15:00, 16:00 GMT
4. **Bot sees 12:00 GMT is in MR window → Trades mean reversion**

### Trading Hours (All in GMT/UTC)

**Mean Reversion:**
- Hours: 05:00, 06:00, 07:00, 09:00, 12:00 GMT
- Days: Monday, Tuesday, Wednesday, Thursday

**Breakout:**
- Hours: 03:00, 14:00, 15:00, 16:00 GMT
- Days: Monday, Tuesday, Friday

**Your MT5 will show different times based on your broker offset!**

---

## EXAMPLES BY BROKER TIMEZONE

### Example 1: GMT+2 Broker (Most EU Brokers)

**Configuration:**
```python
BROKER_GMT_OFFSET = 2
```

**Your MT5 Shows These Times for Mean Reversion:**
- 07:00 broker time = 05:00 GMT ✅
- 08:00 broker time = 06:00 GMT ✅
- 09:00 broker time = 07:00 GMT ✅
- 11:00 broker time = 09:00 GMT ✅
- 14:00 broker time = 12:00 GMT ✅

**Your MT5 Shows These Times for Breakout:**
- 05:00 broker time = 03:00 GMT ✅
- 16:00 broker time = 14:00 GMT ✅
- 17:00 broker time = 15:00 GMT ✅
- 18:00 broker time = 16:00 GMT ✅

---

### Example 2: GMT+3 Broker

**Configuration:**
```python
BROKER_GMT_OFFSET = 3
```

**Your MT5 Shows These Times for Mean Reversion:**
- 08:00 broker time = 05:00 GMT ✅
- 09:00 broker time = 06:00 GMT ✅
- 10:00 broker time = 07:00 GMT ✅
- 12:00 broker time = 09:00 GMT ✅
- 15:00 broker time = 12:00 GMT ✅

---

### Example 3: EST Broker (GMT-5)

**Configuration:**
```python
BROKER_GMT_OFFSET = -5
```

**Your MT5 Shows These Times for Mean Reversion:**
- 00:00 broker time = 05:00 GMT ✅ (midnight!)
- 01:00 broker time = 06:00 GMT ✅
- 02:00 broker time = 07:00 GMT ✅
- 04:00 broker time = 09:00 GMT ✅
- 07:00 broker time = 12:00 GMT ✅

---

## COMMON ISSUES

### Issue: Bot not trading when I expect it to

**Cause:** Wrong broker offset

**Solution:**
1. Double-check your broker's timezone
2. Verify offset calculation: `MT5 time - GMT time`
3. Run test: `python -m trading_bot.strategies.time_filters`
4. Check if conversion is correct

---

### Issue: Bot trading at wrong hours

**Cause:** Offset has wrong sign (+ instead of - or vice versa)

**Solution:**
- If broker is AHEAD of GMT → use + (e.g., +2, +3)
- If broker is BEHIND GMT → use - (e.g., -4, -5)

**Example:**
```
Wrong: BROKER_GMT_OFFSET = -2  (when broker is GMT+2)
Right: BROKER_GMT_OFFSET = 2
```

---

### Issue: Daylight Saving Time Changes

**Some brokers switch between GMT+2 (winter) and GMT+3 (summer)**

**Solution 1 (Manual):**
- Update BROKER_GMT_OFFSET when DST changes
- Usually:
  - GMT+2 (winter): November - March
  - GMT+3 (summer): March - November

**Solution 2 (Check broker):**
- Some brokers use GMT+3 year-round (no DST switching)
- Check your broker's documentation

---

## VERIFICATION CHECKLIST

Before going live:

- [ ] Set BROKER_GMT_OFFSET in strategy_config.py
- [ ] Run test: `python -m trading_bot.strategies.time_filters`
- [ ] Verify timezone conversion is correct
- [ ] Check that trading hours make sense for your broker
- [ ] Compare MT5 time to expected GMT time
- [ ] Test on demo account first

---

## SYMBOLS CONFIGURATION

**Your symbols are still configured:**
- ✅ EURUSD
- ✅ GBPUSD
- ✅ USDJPY

Location: `config/config.yaml` (lines 5-7)

**Nothing was removed** - only timezone handling was added!

---

## FILES MODIFIED

1. `trading_bot/config/strategy_config.py`
   - Added: BROKER_GMT_OFFSET parameter
   - Added: Timezone configuration documentation

2. `trading_bot/strategies/time_filters.py`
   - Added: broker_time_to_gmt() method
   - Added: gmt_to_broker_time() method
   - Updated: All time checks now convert broker time to GMT
   - Added: Timezone conversion tests

---

## SUPPORT

### Need Help?

1. **Check current setup:**
   ```bash
   python -m trading_bot.strategies.time_filters
   ```

2. **View schedule in your broker time:**
   - Look at "TEST SCENARIOS" section
   - Shows both broker time and GMT time
   - Shows which strategy is active

3. **Still confused?**
   - Note: Trading hours in config are ALWAYS in GMT
   - Bot automatically converts your broker's time to GMT
   - You don't need to manually convert anything!

---

**Created:** 2025-12-23
**Status:** ✅ Timezone conversion active
**Default Offset:** 0 (GMT/UTC) - **YOU MUST SET THIS!**
