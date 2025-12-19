# Regime Threshold Optimizer - Usage Guide

## What It Does

Finds the **sweet spot** for regime detection by testing different combinations of:
- **Hurst alone** vs **VHF alone** vs **ADX alone**
- **Hurst + VHF** (current implementation)
- **Hurst + VHF + ADX** (triple confirmation)

Then correlates each combination with actual trade outcomes to find which best predicts wins vs losses.

## The Problem

You have 3 regime indicators:
- **Hurst Exponent**: Measures mean reversion vs trending behavior
- **VHF**: Measures choppiness vs trend strength
- **ADX**: Traditional trend strength indicator

But what thresholds should you use? And which combination works best?

## The Solution

This tool:
1. Gets your last X days of trades
2. Calculates Hurst, VHF, and ADX at each trade entry
3. Tests HUNDREDS of threshold combinations
4. Measures which combo best separates winning ranging trades from losing trending trades
5. Tells you the **optimal thresholds** to use

## Usage

### Basic Usage (GBPUSD, 30 days)
```bash
python optimize_regime_thresholds.py \
    --symbols GBPUSD \
    --days 30 \
    --login 12345 \
    --password "yourpass" \
    --server "Broker-Server"
```

### Multiple Symbols
```bash
python optimize_regime_thresholds.py \
    --symbols EURUSD GBPUSD USDJPY \
    --days 60 \
    --login 12345 \
    --password "yourpass" \
    --server "Broker-Server"
```

### Longer History (60 days)
```bash
python optimize_regime_thresholds.py \
    --symbols GBPUSD \
    --days 60 \
    --login 12345 \
    --password "yourpass" \
    --server "Broker-Server"
```

### Adjust Minimum Trades
```bash
python optimize_regime_thresholds.py \
    --symbols GBPUSD \
    --days 30 \
    --min-trades 15 \  # Require 15+ trades per regime
    --login 12345 \
    --password "yourpass" \
    --server "Broker-Server"
```

## What It Tests

### 1. Hurst Alone
Tests different thresholds:
- Ranging: Hurst < 0.40, 0.42, 0.45, 0.47, 0.50
- Trending: Hurst > 0.50, 0.52, 0.55, 0.57, 0.60

Example result:
```
Ranging (H < 0.45): 28 trades, 72.5% WR ✅
Trending (H > 0.55): 14 trades, 35.7% WR ✅
Score: 136.8
```

### 2. VHF Alone
Tests different thresholds:
- Ranging: VHF < 0.20, 0.23, 0.25, 0.27, 0.30
- Trending: VHF > 0.35, 0.38, 0.40, 0.42, 0.45

### 3. ADX Alone (Baseline)
Tests legacy ADX thresholds:
- Ranging: ADX < 15, 18, 20, 22, 25
- Trending: ADX > 20, 23, 25, 27, 30

### 4. Hurst + VHF (Current Implementation)
Tests combinations:
- Ranging: Hurst < X **AND** VHF < Y
- Trending: Hurst > X **OR** VHF > Y

Example:
```
Ranging (H<0.45 + VHF<0.25): 18 trades, 77.8% WR ✅
Trending (H>0.55 OR VHF>0.40): 22 trades, 31.8% WR ✅
Score: 145.9
```

### 5. Hurst + VHF + ADX (Triple Confirmation)
Tests with ADX as additional filter:
- Ranging: Hurst < X **AND** VHF < Y **AND** ADX < Z
- Trending: Hurst > X **OR** VHF > Y **OR** ADX > Z

Example:
```
Ranging (H<0.45 + VHF<0.25 + ADX<20): 12 trades, 83.3% WR ✅✅
Trending (H>0.55 OR VHF>0.40 OR ADX>25): 26 trades, 30.8% WR ✅
Score: 152.5
```

## Understanding the Score

**Score = Ranging Win Rate + (100 - Trending Win Rate)**

- **Higher ranging WR** = Good (want to win in ranging)
- **Lower trending WR** = Good (want to avoid/lose in trending)
- **Perfect score** = 200 (100% WR in ranging, 0% WR in trending)
- **Best real score** = Usually 140-170

## Example Output

```
================================================================================
🎯 REGIME OPTIMIZATION RESULTS
================================================================================

────────────────────────────────────────────────────────────────────────────────
📊 HURST Alone
────────────────────────────────────────────────────────────────────────────────

   #1: H<0.45_H>0.55
      Score: 136.8
      Ranging: 28 trades, 72.5% WR
      Trending: 14 trades, 35.7% WR
      Coverage: 87.5%

   #2: H<0.47_H>0.55
      Score: 134.2
      Ranging: 24 trades, 70.8% WR
      Trending: 16 trades, 36.5% WR
      Coverage: 83.3%

────────────────────────────────────────────────────────────────────────────────
📊 HURST + VHF (Current)
────────────────────────────────────────────────────────────────────────────────

   #1: H<0.45+VHF<0.25_H>0.55+VHF>0.40
      Score: 145.9
      Ranging: 18 trades, 77.8% WR
      Trending: 22 trades, 31.8% WR
      Coverage: 83.3%

────────────────────────────────────────────────────────────────────────────────
📊 HURST + VHF + ADX
────────────────────────────────────────────────────────────────────────────────

   #1: H<0.45+VHF<0.25+ADX<20
      Score: 152.5
      Ranging: 12 trades, 83.3% WR
      Trending: 26 trades, 30.8% WR
      Coverage: 79.2%

================================================================================
🏆 BEST CONFIGURATION
================================================================================

   Method: HURST + VHF + ADX
   Config: H<0.45+VHF<0.25+ADX<20
   Score: 152.5

   Details:
      Ranging trades: 12 (83.3% WR)
      Trending trades: 26 (30.8% WR)

   📝 Recommended Thresholds:
      HURST_RANGING_THRESHOLD = 0.45
      HURST_TRENDING_THRESHOLD = 0.55
      VHF_RANGING_THRESHOLD = 0.25
      VHF_TRENDING_THRESHOLD = 0.40
      ADX_RANGING_THRESHOLD = 20
      ADX_TRENDING_THRESHOLD = 25

================================================================================
```

## How to Apply Results

### If Hurst Alone Wins:
```python
# In advanced_regime_detector.py
self.hurst_ranging_threshold = 0.45  # Use discovered value
self.hurst_trending_threshold = 0.55

# Disable VHF checks or reduce weight
```

### If Hurst + VHF Wins (likely):
```python
# Current implementation - adjust thresholds
self.hurst_ranging_threshold = 0.45  # Use discovered value
self.hurst_trending_threshold = 0.55
self.vhf_ranging_threshold = 0.25    # Use discovered value
self.vhf_trending_threshold = 0.40
```

### If Hurst + VHF + ADX Wins:
```python
# Need to modify is_safe_for_recovery() to include ADX
def is_safe_for_recovery(self, price_data, adx_threshold=20):
    hurst = self.calculate_hurst_exponent(price_data)
    vhf = self.calculate_vhf(price_data)

    # Calculate ADX (add import from market_analyzer)
    market_condition = MarketAnalyzer().analyze_market_condition(price_data)
    adx = market_condition.get('adx')

    # Triple confirmation for ranging
    if hurst < 0.45 and vhf < 0.25 and adx < 20:
        return True, "✅ RANGING (H+VHF+ADX confluence)"

    # Any trending signal = not safe
    if hurst > 0.55 or vhf > 0.40 or adx > 25:
        return False, "❌ TRENDING (H/VHF/ADX)"
```

## When to Run

### After Significant Trading History
Need at least 30+ trades for statistical significance

### After Market Regime Changes
Bear market → Bull market → different thresholds may work better

### Every 1-3 Months
Market characteristics change over time

### Before Going Live
Optimize on demo/paper trading data first

## Interpreting Results

### High Score (150+)
Excellent separation - thresholds work very well

### Medium Score (130-150)
Good separation - thresholds are decent

### Low Score (<130)
Poor separation - regime detection not helping much

### Coverage Matters
- **High coverage** (80%+) = Most trades classified
- **Low coverage** (< 60%) = Too conservative, missing trades

### Trade Counts Matter
- **12 ranging, 26 trending** = Enough data for both
- **3 ranging, 45 trending** = Not enough ranging data
- **Need 10+ per regime** for statistical validity

## Caveats

1. **Past performance ≠ Future results**
   - Thresholds optimized on past data may not work in future
   - Re-optimize periodically

2. **Overfitting Risk**
   - Don't over-optimize on small datasets
   - Need 50+ total trades minimum

3. **Symbol Dependency**
   - GBPUSD optimal thresholds ≠ USDJPY optimal thresholds
   - Run per symbol or use conservative thresholds

4. **Market Regime Dependency**
   - Bull market thresholds ≠ Bear market thresholds
   - Test on diverse market conditions

## Tips

1. **Start with 60 days** of data for robustness
2. **Run separately per symbol** for best results
3. **Look for consistent winners** across different periods
4. **Don't chase perfect scores** - 140-150 is excellent
5. **Consider coverage** - 100% accuracy on 3 trades means nothing

## Integration with Bot

Once you find optimal thresholds:

1. Update `advanced_regime_detector.py`:
```python
def __init__(
    self,
    hurst_period: int = 100,
    vhf_period: int = 28,
    hurst_ranging_threshold: float = 0.45,  # From optimizer
    hurst_trending_threshold: float = 0.55,  # From optimizer
    vhf_ranging_threshold: float = 0.25,     # From optimizer
    vhf_trending_threshold: float = 0.40     # From optimizer
):
```

2. If triple combo wins, add ADX integration

3. Restart bot with new thresholds

4. Monitor performance for 1-2 weeks

5. Re-run optimizer to verify improvement
