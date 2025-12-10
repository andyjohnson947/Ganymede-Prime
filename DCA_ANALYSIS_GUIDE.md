# DCA Settings Analysis Guide

## How to Find Optimal DCA Settings from Your Trade History

This guide will help you analyze your historical trades to determine the best dollar cost averaging (DCA) settings.

---

## 📥 Step 1: Export Your MT5 Trade History

### Method 1: CSV Export (Recommended)
1. Open **MetaTrader 5** terminal
2. Go to **"Account History"** tab at the bottom
3. Right-click in the history → **"Custom Period"** → Select your date range
4. Right-click again → **"Report"** → **"Open XML"** or **"Detailed Statement"**
5. Save as `.xml` or `.csv` file

### Method 2: Screenshot/Manual Entry
If you have a small number of trades, you can manually create a CSV file with this format:

```csv
Symbol,Type,Volume,Entry Price,Exit Price,Profit,Entry Time,Exit Time,Comment
EURUSD,buy,0.03,1.16464,1.16589,-3.75,2025-12-10 18:30:05,2025-12-10 18:40:06,Confluence:22
EURUSD,sell,0.03,1.16475,1.16589,-3.42,2025-12-10 18:32:05,2025-12-10 18:42:06,Grid L1 - 592470
EURUSD,buy,0.15,1.16475,1.16587,16.80,2025-12-10 18:32:05,2025-12-10 18:42:06,Hedge - 59247059
```

---

## 🔍 Step 2: Run the Analysis

```bash
# Quick analysis (from your CSV)
python import_and_analyze_dca.py trades.csv

# Full comprehensive analysis (after creating database)
python analyze_recovery_strategies.py
```

---

## 📊 What the Analysis Shows

### 1. **DCA Success Rate by Depth**
Shows which number of DCA levels works best:

```
✅ 2 levels: 80.0% win rate (8/10) | Avg P/L: $45.20 | Multiplier: 1.5x
✅ 3 levels: 70.0% win rate (7/10) | Avg P/L: $38.50 | Multiplier: 1.6x
⚠️  4 levels: 50.0% win rate (5/10) | Avg P/L: $12.30 | Multiplier: 1.7x
❌ 5 levels: 30.0% win rate (3/10) | Avg P/L: -$15.40 | Multiplier: 1.8x
```

**Interpretation:**
- **2-3 levels** = Safe and profitable
- **4+ levels** = Risky, lower success rate

### 2. **Optimal Lot Multiplier**
Shows what multiplier works best:

```
Average multiplier: 1.45x
```

**Interpretation:**
- **1.0x** = Fixed lots (no martingale)
- **1.4-1.5x** = Conservative martingale ✅
- **2.0x+** = Aggressive martingale ⚠️

### 3. **Price Decline Analysis**
Shows how far price moved during DCA:

```
Average price decline: 35.5 pips
Max decline before recovery: 82.3 pips
```

**Interpretation:**
- Plan DCA spacing based on typical decline
- Set max DCA levels based on worst-case decline

### 4. **Best vs Worst Scenarios**
Shows actual examples:

```
🏆 Best: 3 levels, EURUSD, $125.50 profit, 1.5x multiplier
⚠️  Worst: 6 levels, EURUSD, -$215.30 loss, 85.6 pips decline
```

---

## 💡 How to Use the Results

### Example Result:
```
✅ Optimal DCA Depth: 3 levels (75.0% success rate)
✅ Recommended Multiplier: 1.45x
```

### Apply to Your Bot:

**Edit `trading_bot/config/strategy_config.py`:**

```python
# DCA Settings (Based on Analysis)
DCA_CONFIG = {
    'enabled': True,
    'max_levels': 3,              # ← From analysis (was 5)
    'lot_multiplier': 1.45,       # ← From analysis (was 1.5)
    'trigger_pips': 12.0,         # Distance between DCA entries
    'max_total_lots': 0.15,       # Safety limit
}
```

**Or edit `src/strategies/recovery_manager.py`:**

```python
class RecoveryManager:
    MAX_RECOVERY_ATTEMPTS = 3     # ← From analysis
    MARTINGALE_MULTIPLIER = 1.45  # ← From analysis
```

---

## 🎯 Real Example Using Your Data

Based on your EURUSD trades screenshot:

### Your Current Settings (Estimated):
- DCA L1, L2, L3, L4 = **4 levels**
- All showing losses = **Not working well**

### What Analysis Might Show:
```
❌ 4 levels: 35% win rate (losing!)
✅ 2 levels: 70% win rate (better)

Recommendation: Reduce to 2-3 DCA levels maximum
```

### Why This Happens:
- More levels = More exposure = Harder to recover
- Fewer levels = Less risk = Higher success rate
- Better to take small loss than deep averaging

---

## 🔄 Step 3: Implement and Test

1. **Update config** with optimal settings
2. **Backtest** on historical data
3. **Paper trade** for 1-2 weeks
4. **Monitor** results
5. **Adjust** if needed

---

## 📈 Advanced Analysis

Once you create the database, run the full analysis:

```bash
python analyze_recovery_strategies.py
```

This provides:
- **Grid analysis** (spacing, levels, success rate)
- **Hedge analysis** (trigger point, ratio, effectiveness)
- **DCA + Grid combinations** (what works together)
- **Timing patterns** (best hours/days)
- **Risk metrics** (max exposure, drawdown)
- **Combined recommendations** (complete strategy optimization)

Output saved to: `recovery_strategy_analysis.json`

---

## ⚠️ Important Warnings

### Red Flags in Analysis:
```
❌ DCA overall success < 50% → Strategy not working
❌ Deep levels (5+) profitable → Risky, may fail in trending market
❌ High multiplier (2.0x+) → Exponential risk growth
```

### Safe Guidelines:
- ✅ Max 3-4 DCA levels
- ✅ Multiplier 1.3-1.6x
- ✅ Success rate > 60%
- ✅ Test on demo first

---

## 📞 Need Help?

If analysis shows unexpected results:

1. **Check data quality**
   - All trades included?
   - Correct entry/exit prices?
   - Valid timestamps?

2. **Check trade classification**
   - Are DCA trades properly detected?
   - Check "Comment" field for patterns
   - Verify same-direction grouping

3. **Review market conditions**
   - Strong trends = DCA fails
   - Ranging markets = DCA works
   - Consider adding trend filter

---

## 📝 Quick Checklist

- [ ] Export MT5 trade history to CSV
- [ ] Run `import_and_analyze_dca.py trades.csv`
- [ ] Review success rates by depth
- [ ] Note optimal levels and multiplier
- [ ] Update bot configuration
- [ ] Backtest with new settings
- [ ] Paper trade to verify
- [ ] Monitor and adjust

---

**Remember:** Historical performance doesn't guarantee future results. Always test new settings on demo accounts first!
