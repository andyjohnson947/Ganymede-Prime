# Breakout Detector - Continuous Monitoring Guide

## Purpose

This monitoring script runs the breakout detector continuously over multiple days, scanning for signals at regular intervals and logging all results.

## Usage

### Basic Usage (Single Symbol, 60-minute intervals)

```bash
python monitor_breakout_signals.py <login> <password> <server>
```

Example:
```bash
python monitor_breakout_signals.py 12345 "yourpass" "VantageInternational-Demo"
```

This will monitor **EURUSD** every **60 minutes** by default.

### Multi-Symbol Monitoring

```bash
python monitor_breakout_signals.py <login> <password> <server> "EURUSD,GBPUSD,USDJPY"
```

Monitors multiple symbols (comma-separated, no spaces).

### Custom Scan Interval

```bash
python monitor_breakout_signals.py <login> <password> <server> EURUSD 30
```

This scans **EURUSD** every **30 minutes**.

### Full Example

```bash
python monitor_breakout_signals.py 12345 "yourpass" "VantageInternational-Demo" "EURUSD,GBPUSD,USDJPY,AUDUSD" 45
```

Monitors 4 symbols every 45 minutes.

## What It Does

### Every Scan:
1. Connects to MT5
2. Fetches H1/Daily/Weekly data for each symbol
3. Calculates all indicators (VWAP, Volume Profile, ADX)
4. Runs volume analysis
5. Checks for breakout signals
6. Logs results
7. Displays current market conditions
8. Waits for next interval

### Console Output:

```
================================================================================
BREAKOUT MONITOR - Scan #5
Time: 2025-12-11 14:30:00
================================================================================

📊 EURUSD
   Price: 1.05234
   ADX: 32.5 (Trending)
   VWAP Distance: 0.88% (Above)
   LVN Percentile: 28th
   Volume: 75th percentile (good) - CONFIRM

   🚀 SIGNAL DETECTED!
      Direction: LONG
      Entry: 1.05240
      SL: 1.05040 | TP: 1.05640
      R:R 1:2.00
      Score: 7 | Factors: at_lvn, vwap_directional_bias, high_volume, trending_adx

📊 GBPUSD
   Price: 1.27145
   ADX: 18.2 (Ranging)
   VWAP Distance: 0.12% (Above)
   Volume: 45th percentile (weak) - REJECT
   ⏸️  No signal

================================================================================
Total Scans: 5
Total Signals: 2
Last Signal: 2025-12-11 12:15:00
Runtime: 4:30:00
Next scan in 60 minutes
Logs: /home/user/Ganymede-Prime/logs/breakout_monitoring
================================================================================
```

## Log Files

All logs are saved in: `logs/breakout_monitoring/`

### 1. `scan_history.log`
Complete history of all scans with market conditions for each symbol:

```
[2025-12-11 14:30:00] Scan #5
Symbols: 2
  EURUSD: 🚀 SIGNAL | ADX=32.5 | VWAP Dist=0.88% | LVN=28th | Vol=75th (good)
    → LONG @ 1.05240 | Score: 7 | R:R 1:2.00
  GBPUSD: ⏸️  No signal | ADX=18.2 | VWAP Dist=0.12% | LVN=65th | Vol=45th (weak)
```

### 2. `signals_summary.log`
Detailed log of all detected signals:

```
================================================================================
🚀 SIGNAL DETECTED: EURUSD - 20251211_143000
================================================================================
Direction: LONG
Entry Type: conservative_retest
Entry Price: 1.05240
Stop Loss: 1.05040
Take Profit: 1.05640
Risk/Reward: 1:2.00
Confluence Score: 7
Factors: at_lvn, vwap_directional_bias, high_volume, trending_adx

Current Price: 1.05234
ADX: 32.5
VWAP Distance: 0.88%
Volume: 75th percentile (good)
```

### 3. `signal_<timestamp>_<symbol>.json`
Individual JSON file for each signal with complete data:

```json
{
  "symbol": "EURUSD",
  "timestamp": "2025-12-11T14:30:00",
  "current_price": {
    "bid": 1.05232,
    "ask": 1.05234,
    "close": 1.05234
  },
  "signal": {
    "direction": "long",
    "entry_type": "conservative_retest",
    "entry_price": 1.05240,
    "stop_loss": 1.05040,
    "take_profit": 1.05640,
    "confluence_score": 7,
    "factors": ["at_lvn", "vwap_directional_bias", "high_volume", "trending_adx"],
    "risk_reward": 2.0
  }
}
```

### 4. `errors.log`
Any connection or data fetch errors.

## Running in Background

### Linux/Mac:
```bash
# Run in background with nohup
nohup python monitor_breakout_signals.py 12345 "yourpass" "VantageInternational-Demo" > monitor.out 2>&1 &

# Check if running
ps aux | grep monitor_breakout

# Stop monitoring
pkill -f monitor_breakout_signals
```

### Windows PowerShell:
```powershell
# Run in separate window
Start-Process python -ArgumentList "monitor_breakout_signals.py 12345 'yourpass' 'VantageInternational-Demo'" -WindowStyle Minimized

# Or use Task Scheduler for persistent monitoring
```

## Stopping the Monitor

Press **Ctrl+C** to stop monitoring gracefully.

The monitor will display final statistics:

```
================================================================================
MONITORING STOPPED
================================================================================
Total Runtime: 2 days, 3:45:12
Total Scans: 75
Total Signals: 8
Logs saved to: /home/user/Ganymede-Prime/logs/breakout_monitoring
================================================================================
```

## Recommended Settings

### For 2-3 Day Evaluation:

**Conservative (less frequent scans, saves resources):**
```bash
python monitor_breakout_signals.py <login> <password> <server> EURUSD 120
```
Scans every 2 hours (12 scans per day).

**Moderate (balanced):**
```bash
python monitor_breakout_signals.py <login> <password> <server> EURUSD 60
```
Scans every hour (24 scans per day).

**Aggressive (catches more opportunities):**
```bash
python monitor_breakout_signals.py <login> <password> <server> EURUSD 30
```
Scans every 30 minutes (48 scans per day).

### Multi-Symbol Recommendation:

```bash
python monitor_breakout_signals.py <login> <password> <server> "EURUSD,GBPUSD,USDJPY" 60
```

Monitor 3 major pairs every hour for broader coverage.

## What to Look For

After running for 2-3 days, analyze the logs:

### Signal Quality:
- How many signals were detected?
- What confluence scores did they have?
- What entry types (conservative_retest vs aggressive_breakout)?

### Market Conditions:
- When do signals typically occur?
- What ADX ranges produce signals?
- Volume patterns during signals?

### Frequency:
- Too many signals? (May need higher confluence threshold)
- Too few signals? (May need to lower requirements or add more symbols)

## Next Steps

1. **Run for 2-3 days** and collect data
2. **Review `signals_summary.log`** for all detected signals
3. **Analyze patterns** in timing and conditions
4. **Evaluate signal quality** based on confluence scores
5. **Decide if ready** for paper trading integration

## Troubleshooting

### No signals detected:
- Check ADX values (need ADX >= 25 for trending market)
- Check volume percentiles (need >= 70th percentile or 1.5x average)
- Check LVN percentiles (need < 30th to be at LVN)
- May need to add more symbols or wait for trending conditions

### Connection errors:
- Check MT5 is running
- Verify credentials and server name
- Check internet connection
- Review `errors.log` for details

### High CPU/Memory usage:
- Increase scan interval (e.g., 120 or 180 minutes)
- Reduce number of symbols

## Safety Note

This monitoring script **DOES NOT trade**. It only:
- Scans market conditions
- Detects potential signals
- Logs results

No orders will be placed. This is purely for evaluation and data collection.
