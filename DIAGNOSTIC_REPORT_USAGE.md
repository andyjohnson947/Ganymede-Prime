# Diagnostic Report Generator - Usage Guide

## What It Does

The Diagnostic Report Generator analyzes your trading history to tell you:

✅ **What's Working** - Keep doing this
❌ **What's Broken** - Fix or remove this
🔧 **What Needs Tuning** - Adjust parameters

## Specific Analysis

### 1. Regime Detection Accuracy
- Did Hurst + VHF correctly identify ranging vs trending markets?
- Are trades in "RANGING" markets actually winning?
- Are recovery blocks justified? (preventing losses vs false positives)
- **Verdict**: Is regime detection working or needs adjustment?

### 2. Confluence Factor Effectiveness
- Which factors correlate with wins? (VWAP bands, POC, LVN, swing levels, HTF)
- Which factors correlate with losses?
- Do higher confluence scores actually perform better?
- **Verdict**: Should any factors be removed or prioritized?

### 3. Recovery Mechanism Performance
- Grid: Helping or hurting?
- Hedge: Worth the risk?
- DCA: Effective or digging deeper?
- **Verdict**: Should any be disabled or tuned?

### 4. Strategy Mode Performance
- Breakout vs Mean Reversion: which works better?
- Are they being used in the right conditions?
- **Verdict**: Should one be disabled?

### 5. Actionable Recommendations
Prioritized list of actions:
- 🔴 **HIGH**: Fix immediately (critical issues)
- 🟡 **MEDIUM**: Tune soon (marginal performance)
- 🟢 **LOW**: Optional improvements

## Usage

### Basic Usage (7 days)
```bash
python generate_diagnostic_report.py --days 7
```

### Custom Time Period (14 days)
```bash
python generate_diagnostic_report.py --days 14
```

### With MT5 Connection (for price correlation)
```bash
python generate_diagnostic_report.py \
    --days 7 \
    --login 12345 \
    --password "yourpass" \
    --server "Broker-Server"
```

### Custom Data Directory
```bash
python generate_diagnostic_report.py \
    --days 7 \
    --data-dir /path/to/diagnostics
```

### Adjust Minimum Trades Threshold
```bash
python generate_diagnostic_report.py \
    --days 7 \
    --min-trades 10  # Require 10+ trades for analysis
```

## Example Output

```
================================================================================
📊 DIAGNOSTIC REPORT
================================================================================
Period: Last 7 days
Generated: 2025-01-15T10:30:00
Total Trades: 42
================================================================================

🎯 REGIME DETECTION ACCURACY
────────────────────────────────────────────────────────────────────────────────

Ranging Market Performance:
   Total trades: 28
   Win rate: 71.4%
   Verdict: EXCELLENT - Ranging regime detection is accurate

Trending Market Performance:
   Total trades: 14
   Win rate: 35.7%
   Verdict: EXCELLENT - Correctly avoiding trending markets

Recovery Blocks:
   Total blocks: 12
   Justified: 10 (83.3%)
   False positives: 2
   Verdict: EXCELLENT - Blocks are preventing losses

🔍 CONFLUENCE EFFECTIVENESS
────────────────────────────────────────────────────────────────────────────────

By Factor:
   ✅ vwap_band_1: 78.6% WR (14 trades) - EXCELLENT - Keep this factor
   ✅ poc: 75.0% WR (16 trades) - EXCELLENT - Keep this factor
   ✅ htf_h4: 72.2% WR (18 trades) - GOOD - Factor is helping
   ⚠️  swing_high: 52.0% WR (25 trades) - NEUTRAL - Factor not adding much value
   ❌ lvn: 38.5% WR (13 trades) - POOR - Consider removing this factor

By Score:
   Score 4: 65.0% WR (20 trades, $142.50)
   Score 5: 72.0% WR (15 trades, $198.20)
   Score 6: 80.0% WR (5 trades, $85.00)
   Score 7+: 100.0% WR (2 trades, $45.00)

✨ 'vwap_band_1' is your best factor (78.6% WR)
⚠️  'lvn' is dragging down performance (38.5% WR) - CONSIDER REMOVING
📊 EXCELLENT - Higher scores perform better (system working as designed)

🔧 RECOVERY MECHANISMS
────────────────────────────────────────────────────────────────────────────────

   ✅ GRID:
      Triggered: 18 times
      Success rate: 61.1%
      Avg profit: $12.50
      Total profit: $225.00
      Verdict: GOOD - Worth keeping

   ⚠️  HEDGE:
      Triggered: 8 times
      Success rate: 37.5%
      Avg profit: -$8.20
      Total profit: -$65.60
      Verdict: MARGINAL - Consider tuning parameters

   ❌ DCA:
      Triggered: 12 times
      Success rate: 25.0%
      Avg profit: -$15.30
      Total profit: -$183.60
      Verdict: POOR - Consider disabling

📈 STRATEGY MODE PERFORMANCE
────────────────────────────────────────────────────────────────────────────────

   ✅ BREAKOUT:
      Total trades: 15
      Win rate: 80.0%
      Avg profit: $18.50
      Total profit: $277.50

   ✅ MEAN REVERSION:
      Total trades: 27
      Win rate: 63.0%
      Avg profit: $12.30
      Total profit: $332.10

   📊 Breakout outperforming Mean Reversion by 17.0% - Consider focusing on breakouts

💡 ACTIONABLE RECOMMENDATIONS
────────────────────────────────────────────────────────────────────────────────

   🔴 [HIGH] RECOVERY - REMOVE
      Disable DCA - not effective in current market conditions

   🟡 [MEDIUM] CONFLUENCE - REMOVE
      Remove 'lvn' factor - only 38.5% WR

   🟡 [MEDIUM] RECOVERY - TUNE
      Adjust HEDGE parameters - marginal performance

================================================================================
```

## When to Run

### Daily
After 24 hours of trading to check short-term performance

### Weekly
Every Monday to analyze past week and plan adjustments

### After Changes
After modifying any settings to verify impact

### After Market Regime Changes
When you notice market behavior shifting

## Understanding Results

### Regime Detection
- **Ranging trades should win 60%+** - If lower, detector may have false positives
- **Trending trades should lose or break even** - If winning too much, detector too conservative
- **Recovery blocks should be 70%+ justified** - If lower, losing opportunities

### Confluence Factors
- **60%+ win rate = Good factor** - Keep it
- **45-60% = Neutral** - Not adding much value
- **< 45% = Bad factor** - Consider removing

### Recovery Mechanisms
- **55%+ success rate = Worth keeping**
- **40-55% = Marginal, needs tuning**
- **< 40% = Disable it**

### Strategy Modes
- **Compare win rates** - Big difference (20%+) means focus on the winner
- **Check total trades** - Need 10+ trades per strategy for significance

## Tips

1. **Wait for sufficient data** - Need at least 5 trades for meaningful analysis
2. **Run after major changes** - Always verify impact of config changes
3. **Check during different market conditions** - Trending vs ranging markets
4. **Compare reports over time** - Track if recommendations improve performance
5. **Don't overreact to single reports** - Look for consistent patterns

## Integration with Bot

The diagnostic module automatically:
- Records every trade close
- Logs every recovery action
- Captures market conditions hourly

This report generator pulls all that data and correlates it to answer "what's working?"

## Next Steps After Report

Based on recommendations:

### High Priority (Fix Now)
```python
# Example: Disable underperforming recovery
# In strategy_config.py
ENABLE_DCA = False  # If report says DCA not working

# Example: Remove bad confluence factor
# In signal_detector.py
# Comment out or reduce weight of underperforming factors
```

### Medium Priority (Tune Soon)
```python
# Example: Adjust hedge parameters
HEDGE_DISTANCE_PIPS = 10  # Increase from 8 if too aggressive
HEDGE_MULTIPLIER = 4.0    # Reduce from 5.0 if too risky
```

### Track Changes
After making changes, wait 3-7 days and run report again to verify improvement.
