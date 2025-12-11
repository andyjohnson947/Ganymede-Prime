# Breakout Trader - Quick Start Guide

## 🚀 Ready to Trade!

The breakout trader is now ready to place actual trades on your demo account.

## ⚙️ Configuration First

Before running, check your settings in `breakout_strategy/config/breakout_config.py`:

### **Paper Trading Mode** (Line 21)
```python
BREAKOUT_PAPER_TRADE_ONLY = True  # Set False for live trading
```

- `True` = Logs signals but **doesn't place orders** (safe testing)
- `False` = Places **real orders** via MT5

### **Risk Settings** (Lines 96-108)
```python
BREAKOUT_RISK_PERCENT = 0.75  # 0.75% per trade
BREAKOUT_STOP_LOSS_PIPS = 20  # Default stop
BREAKOUT_TP_RATIO = 2.0  # 1:2 R:R minimum
```

### **Entry Types** (Lines 126-131)
```python
ALLOW_AGGRESSIVE_ENTRY = False  # Immediate breakout (disabled)
ALLOW_CONSERVATIVE_ENTRY = True  # Pullback/retest (enabled)
```

### **Safety Limits** (Lines 23-27)
```python
BREAKOUT_MAX_CONSECUTIVE_LOSSES = 3  # Auto-disable after 3 losses
BREAKOUT_MAX_DAILY_LOSS_PCT = 2.0  # Auto-disable if lose 2% of account
```

## 🎯 How to Run

### **1. Start Trading (Default: Paper Mode)**

```bash
python run_breakout_trader.py <login> <password> <server>
```

Example:
```bash
python run_breakout_trader.py 99691609 "-v6sDvEf" MetaQuotes-Demo
```

This will:
- Trade **EURUSD** only
- Scan every **60 minutes**
- Run in **paper mode** (if enabled in config)

### **2. Multiple Symbols**

```bash
python run_breakout_trader.py 99691609 "-v6sDvEf" MetaQuotes-Demo "EURUSD,GBPUSD,USDJPY"
```

### **3. Custom Scan Interval**

```bash
# Scan every 30 minutes
python run_breakout_trader.py 99691609 "-v6sDvEf" MetaQuotes-Demo EURUSD 30

# Scan every 2 hours (120 minutes)
python run_breakout_trader.py 99691609 "-v6sDvEf" MetaQuotes-Demo EURUSD 120
```

## 📊 What You'll See

### **On Startup:**
```
================================================================================
BREAKOUT TRADER CONFIGURATION
================================================================================
⚠️  PAPER TRADING MODE - No real orders will be placed
Symbols: EURUSD
Risk per trade: 0.75%
Min confluence: 6
Conservative entry: True
Aggressive entry: False
Trailing stop: True
Breakeven move: True
Scan interval: 60 minutes
================================================================================
Connected to MetaQuotes-Demo
Account: 99691609 | Balance: $10000.00

🚀 BREAKOUT TRADER STARTING
Press Ctrl+C to stop
```

### **During Scanning:**
```
================================================================================
SCANNING FOR BREAKOUT SIGNALS - 2025-12-11 15:30:00
================================================================================
⏸️  EURUSD: No signal | ADX: 18.2 | Vol: 45th
```

### **When Signal Found (Paper Mode):**
```
🚀 SIGNAL: EURUSD LONG | Score: 7
📝 PAPER TRADE: LONG EURUSD @ 1.05240
   SL: 1.05040 | TP: 1.05640 | Score: 7
```

### **When Signal Found (Live Mode):**
```
🚀 SIGNAL: EURUSD LONG | Score: 7
✅ TRADE OPENED: LONG EURUSD 0.15 lots @ 1.05240
   Ticket: 123456789 | SL: 1.05040 | TP: 1.05640
   Entry: conservative_retest | Score: 7
```

### **Position Management:**
```
📍 Moved to breakeven: Ticket 123456789 | SL: 1.05240
🔄 Trailing stop activated: Ticket 123456789
📈 Trailing SL updated: Ticket 123456789 | SL: 1.05450
```

### **Trade Closed:**
```
✅ WIN: Ticket 123456789 | P&L: $30.00
```

### **Statistics:**
```
================================================================================
BREAKOUT TRADER STATISTICS
================================================================================
Runtime: 2:45:30
Signals Detected: 3
Trades Opened: 2
Trades Closed: 1
Wins: 1 | Losses: 0
Win Rate: 100.0%
Total P&L: $30.00
Open Positions: 1
================================================================================
```

## 📁 Log Files

All logs saved to: `logs/breakout_trading/`

### **1. `breakout_trader_YYYYMMDD.log`**
Complete activity log with timestamps

### **2. `signals_YYYYMMDD.log`**
All signals detected with full details

## 🛑 Stopping the Trader

Press **Ctrl+C** to stop gracefully.

The trader will:
1. Complete current scan
2. Show final statistics
3. Disconnect from MT5
4. Save all logs

**Note:** Open positions will **NOT** be closed automatically. You can:
- Let them hit TP/SL
- Close manually in MT5
- Restart the trader (it will resume managing them)

## ⚠️ Safety Features

### **Auto-Disable Protection:**

The trader will **automatically disable itself** if:
- 3 consecutive losses
- Daily loss exceeds 2% of account
- Win rate < 45% over last 20 trades

When disabled:
```
🛑 AUTO-DISABLE: 3 consecutive losses
Review performance and re-enable manually if needed
```

You'll need to review and manually re-enable in config.

### **Magic Number Separation:**

- Breakout trades: Magic **234001**
- Reversion trades: Magic **234000**

The trader **ONLY** manages positions with magic 234001, so it won't interfere with reversion module trades.

## 🎮 Enabling Live Trading

**After testing in paper mode**, to enable live trading:

1. Edit `breakout_strategy/config/breakout_config.py`
2. Change line 21:
   ```python
   BREAKOUT_PAPER_TRADE_ONLY = False  # NOW LIVE!
   ```
3. Restart the trader

**⚠️ Warning:** This will place **real orders** on your demo account!

## 📈 Recommended Testing Approach

### **Phase 1: Paper Trading (1-2 days)**
```python
BREAKOUT_PAPER_TRADE_ONLY = True
```
- See how many signals are detected
- Review signal quality
- Check confluence scores

### **Phase 2: Live Demo Trading (3-5 days)**
```python
BREAKOUT_PAPER_TRADE_ONLY = False
```
- Place real orders on **demo account**
- Monitor actual execution
- Track win rate and P&L
- Verify position management (breakeven, trailing)

### **Phase 3: Production (After validation)**
- Only if Phase 2 shows good results
- Monitor closely for first week
- Be ready to disable if performance degrades

## 🔍 Monitoring Tips

### **Check Logs Regularly:**
```bash
# View today's log
tail -f logs/breakout_trading/breakout_trader_20251211.log

# View signals
cat logs/breakout_trading/signals_20251211.log
```

### **Check Open Positions in MT5:**
Filter by Magic: **234001**

### **Review Statistics:**
The trader shows stats after each scan cycle

## ❓ Troubleshooting

### **No Signals Detected:**
- Check ADX values (need >= 25 for trending)
- Check volume (need >= 70th percentile)
- May need to add more symbols or wait for trending conditions
- Review last scan output for reasons

### **Connection Errors:**
- Verify MT5 is running
- Check credentials
- Ensure server name is correct

### **Orders Rejected:**
- Check account has sufficient margin
- Verify symbol is available
- Check lot size calculation

## 🆚 Reversion Module Compatibility

**100% Compatible!** Both can run simultaneously:

| Module | Magic | Config | Trades When |
|--------|-------|--------|-------------|
| Reversion | 234000 | `trading_config.py` | ADX < 25 (ranging) |
| Breakout | 234001 | `breakout_config.py` | ADX >= 25 (trending) |

They won't interfere with each other.

## 🎯 Quick Command Reference

```bash
# Paper trading, single symbol, 60 min scans
python run_breakout_trader.py <login> <password> <server>

# Paper trading, multiple symbols
python run_breakout_trader.py <login> <password> <server> "EURUSD,GBPUSD,USDJPY"

# Paper trading, faster scans (30 min)
python run_breakout_trader.py <login> <password> <server> EURUSD 30

# Live trading (after enabling in config)
python run_breakout_trader.py <login> <password> <server> EURUSD 60
```

## 🚦 Current Status

- ✅ Breakout detector: Complete and tested
- ✅ Trade execution: Ready
- ✅ Position management: Breakeven, trailing stops, time exits
- ✅ Safety features: Auto-disable, risk limits
- ✅ Logging: Complete activity tracking
- ⚠️ Paper mode: **ENABLED by default**
- ⏸️ Live mode: Disabled (enable after testing)

---

**Ready to test?** Start with paper trading and see how it performs!
