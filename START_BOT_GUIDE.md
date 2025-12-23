# 🚀 BOT STARTUP GUIDE (Windows)

## Step 1: Install MetaTrader5 Package

Open PowerShell and run:
```powershell
cd C:\git\Ganymede-Prod
pip install MetaTrader5
```

**Verify it installed:**
```powershell
python -c "import MetaTrader5 as mt5; print('✅ MT5 package installed')"
```

---

## Step 2: Open MT5 Terminal

1. Launch **MetaTrader 5** application
2. **Login to your account**
3. **Leave it running** in the background

---

## Step 3: Start the Trading Bot

**In PowerShell, run:**
```powershell
cd C:\git\Ganymede-Prod

python trading_bot\main.py --login YOUR_ACCOUNT_NUMBER --password "YOUR_PASSWORD" --server "YOUR_BROKER_SERVER"
```

**Example:**
```powershell
python trading_bot\main.py --login 12345678 --password "MyPass123" --server "ICMarkets-Demo"
```

---

## Step 4: Verify Bot is Running

**You should see output like:**
```
================================================================================
     CONFLUENCE TRADING BOT - UPGRADED
     Timezone-Aware | Instrument-Specific Trading Windows
================================================================================

✅ Connected to MT5
   Account: 12345678
   Balance: $10000.00
   Equity: $10000.00
   Server: ICMarkets-Demo

🚀 CONFLUENCE STRATEGY STARTING
...
```

**The bot will keep running and checking for signals.**

---

## Step 5: Check Logs (In a NEW PowerShell Window)

**While bot is running, open a NEW PowerShell window:**
```powershell
cd C:\git\Ganymede-Prod
Get-Content trading_bot\trading_bot.log -Tail 50 -Wait
```

**You should see:**
- "Refreshing market data for EURUSD"
- "Checking signals for EURUSD"
- "Checking signals for GBPUSD"

---

## ⚠️ TROUBLESHOOTING

### Problem: "No module named MetaTrader5"
**Solution:** Install it
```powershell
pip install MetaTrader5
```

### Problem: "Failed to connect to MT5"
**Solution:** 
1. Make sure MT5 terminal is open
2. Make sure you're logged in to your account
3. Check your credentials are correct

### Problem: "Log file doesn't exist"
**Solution:** The bot isn't running yet!
- Start the bot first (Step 3)
- THEN check logs (Step 5)

### Problem: Bot crashes immediately
**Solution:** Check what error appears when you start it
- Share the error message for help

---

## 🎯 WHAT TO EXPECT

**After starting:**
- Bot connects to MT5
- Checks EURUSD and GBPUSD every minute
- Waits for signal conditions to align
- **May not trade immediately** - this is normal!

**Signals are selective:**
- Historical: ~413 trades over extended period
- 64.3% win rate = very patient strategy
- May go hours without signals
- **This is intentional - quality over quantity**

---

## 📊 CURRENT TRADING WINDOWS

**Right now (based on time):**
- If 03:00 GMT: Breakout window
- If 05:00-07:00, 09:00, 12:00 GMT: Mean reversion window  
- If 14:00-16:00 GMT: Breakout window
- Otherwise: No trading window (bot waits)

---

## ✅ SUCCESS CHECKLIST

- [ ] MetaTrader5 package installed
- [ ] MT5 terminal open and logged in
- [ ] Bot started with correct credentials
- [ ] Bot shows "Connected to MT5" message
- [ ] Log file exists and shows activity
- [ ] No errors appearing

**Once all checked, bot is running correctly!** 🚀
