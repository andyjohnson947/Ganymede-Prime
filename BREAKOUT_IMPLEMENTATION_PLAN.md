# LVN Breakout Module - Implementation Plan
## Phased Rollout (Option 3) - REVERSION MODULE UNTOUCHED

**CRITICAL CONSTRAINT**: Zero changes to existing mean reversion module (currently in testing)

---

## Backtest Validation Results ✅

| Metric | Mean Reversion (ADX ≥ 25) | LVN Breakout (ADX ≥ 25) | Improvement |
|--------|---------------------------|-------------------------|-------------|
| Trades | 101 | 44 | - |
| Win Rate | 62.4% | 56.8% | -5.6% |
| **Avg Profit/Trade** | **$0.43** | **$5.09** | **+1,082%** |
| Total P/L | $42.64 | $223.96 | +425% |
| Risk/Reward | 1:0.60 | 1:1.83 | +205% |

**Conclusion**: LVN Breakout performs **10x better per trade** in trending markets

**Optimal Confluence Score**: 6+ (60% WR, $10.90 avg profit)

---

## Phase 1: Foundation (Days 1-2)
**Goal**: Build breakout detector WITHOUT touching reversion module

### Day 1: Breakout Detector Core

**File**: `trading_bot/strategies/breakout_detector.py` (NEW)

```python
"""
LVN Breakout Signal Detector
Operates independently from mean reversion module
Uses VWAP-supported LVN breakouts in trending markets (ADX >= 25)
"""

class BreakoutDetector:
    """
    Detects breakout signals using LVN + VWAP confluence

    Entry Criteria:
    1. ADX >= 25 (trending market)
    2. At or near LVN (low volume node)
    3. VWAP directional bias (above = long, below = short)
    4. Volume expansion (optional)
    5. Minimum confluence score: 6
    """

    def __init__(self):
        self.vwap = VWAP()  # Reuse existing indicator
        self.volume_profile = VolumeProfile()  # Reuse existing
        self.min_confluence = 6  # From backtest: scores < 6 underperform

    def detect_breakout(self, data, symbol):
        """Detect LVN breakout opportunities"""
        # Independent from signal_detector.py
        pass
```

**Confluence Weights** (from backtest):
```python
BREAKOUT_CONFLUENCE = {
    'at_lvn': 3,                    # Critical - low resistance
    'near_lvn': 2,                  # Near LVN area
    'strong_trend_adx_35': 2,       # ADX >= 35
    'trending_adx_25': 1,           # ADX 25-35
    'vwap_directional_bias': 2,     # Strong bias (>0.1%)
    'vwap_neutral_bias': 1,         # Weak bias
    'high_volume_70th': 2,          # Volume > 70th percentile
    'above_avg_volume': 1,          # Volume > 50th percentile
    'away_from_poc': 1,             # Not in consolidation
    'vwap_outer_band': 1,           # At ±2σ or ±3σ band
}
```

**Status**: ❌ Not started

---

### Day 1-2: Volume Analyzer

**File**: `trading_bot/indicators/volume_analyzer.py` (NEW)

```python
"""
Volume Expansion Analyzer
Detects volume surges for breakout confirmation
"""

class VolumeAnalyzer:
    """
    Analyzes volume patterns for breakout validation

    Features:
    - Volume percentile (vs recent average)
    - Volume expansion detection (>130%, >180%)
    - Volume profile integration
    """

    def calculate_volume_percentile(self, current_volume, lookback=20):
        """Calculate volume percentile vs recent average"""
        pass

    def is_volume_expansion(self, current_volume, threshold=1.3):
        """Check if volume is expanding (breakout confirmation)"""
        pass
```

**Status**: ❌ Not started

---

### Day 2: Configuration

**File**: `trading_bot/config/breakout_config.py` (NEW)

```python
"""
Breakout Module Configuration
Completely separate from mean reversion config
"""

# =============================================================================
# BREAKOUT MODULE CONTROL
# =============================================================================

BREAKOUT_MODULE_ENABLED = False  # KILL SWITCH - disabled by default
BREAKOUT_PAPER_TRADE_ONLY = True  # Paper trade first, then enable live

# =============================================================================
# MARKET CONDITION ROUTING
# =============================================================================

# ADX thresholds (from backtest analysis)
BREAKOUT_ADX_MIN = 25           # Minimum trending strength
BREAKOUT_ADX_OPTIMAL = 30       # Optimal for breakouts
BREAKOUT_ADX_MAX = 50           # Above this = extreme caution

# =============================================================================
# LVN BREAKOUT CONFLUENCE (From Backtest)
# =============================================================================

MIN_BREAKOUT_CONFLUENCE = 6     # Optimized from backtest (not 4)
                                # Score 6: 60% WR, $10.90 avg
                                # Scores 4-5: Poor performance

BREAKOUT_CONFLUENCE_WEIGHTS = {
    'at_lvn': 3,
    'near_lvn': 2,
    'strong_trend_adx': 2,
    'trending_adx': 1,
    'vwap_directional_bias': 2,
    'vwap_neutral_bias': 1,
    'high_volume': 2,
    'above_avg_volume': 1,
    'away_from_poc': 1,
    'vwap_outer_band': 1,
}

# =============================================================================
# RISK MANAGEMENT (More conservative than reversion)
# =============================================================================

BREAKOUT_RISK_PERCENT = 0.75    # 0.75% per trade (vs 1% for reversion)
BREAKOUT_MAX_EXPOSURE = 4.0     # Max total lots (vs 5.04 for reversion)
BREAKOUT_STOP_PIPS = 20         # Wider stops for breakouts
BREAKOUT_RR_RATIO = 2.0         # 1:2 minimum

# =============================================================================
# EXIT RULES
# =============================================================================

USE_TRAILING_STOP = True
TRAILING_ACTIVATION_RR = 1.5    # Activate after 1.5x risk in profit
TRAILING_DISTANCE_ATR = 2.0     # Trail 2 ATR behind price
MAX_HOLD_HOURS = 72             # Close after 3 days if stalled

EXIT_ON_ADX_DECLINE = True      # Exit when ADX declining + < 25
EXIT_ON_OPPOSITE_SIGNAL = True  # Exit on reverse breakout
```

**Status**: ❌ Not started

---

## Phase 2: Integration (Days 3-4)
**Goal**: Connect breakout module WITHOUT modifying reversion

### Day 3: Strategy Router

**File**: `trading_bot/strategies/strategy_router.py` (NEW)

```python
"""
Strategy Router - Routes to breakout OR reversion (never both)
Does NOT modify existing confluence_strategy.py
"""

from strategies.signal_detector import SignalDetector
from strategies.breakout_detector import BreakoutDetector
from indicators.adx import calculate_adx
from config.breakout_config import (
    BREAKOUT_MODULE_ENABLED,
    BREAKOUT_ADX_MIN
)

class StrategyRouter:
    """
    Routes symbol to appropriate strategy based on market condition

    CRITICAL: Only ONE strategy active per symbol at a time
    """

    def __init__(self):
        self.reversion_detector = SignalDetector()  # Existing, unchanged
        self.breakout_detector = BreakoutDetector()  # New, optional

    def get_strategy_for_symbol(self, symbol, market_data):
        """
        Determine which strategy to use

        Returns:
            'reversion' | 'breakout' | None
        """

        # Calculate market condition
        adx = calculate_adx(market_data)

        # If breakout module disabled, always use reversion
        if not BREAKOUT_MODULE_ENABLED:
            return 'reversion'

        # Route based on ADX
        if adx < BREAKOUT_ADX_MIN:
            return 'reversion'  # Ranging market
        else:
            return 'breakout'   # Trending market

    def detect_signal(self, symbol, market_data):
        """
        Detect signal using appropriate strategy

        Returns signal from EITHER reversion OR breakout (never both)
        """
        strategy = self.get_strategy_for_symbol(symbol, market_data)

        if strategy == 'reversion':
            return self.reversion_detector.detect_signal(...)
        elif strategy == 'breakout':
            return self.breakout_detector.detect_breakout(...)
        else:
            return None
```

**Status**: ❌ Not started

---

### Day 3-4: Optional Integration Point

**File**: `trading_bot/strategies/confluence_strategy.py` (OPTIONAL CHANGE)

**IF you want to enable routing** (optional, can skip this):

```python
# OPTIONAL: Add router support (can be disabled via config)
from config.breakout_config import BREAKOUT_MODULE_ENABLED

class ConfluenceStrategy:
    def __init__(self, mt5_manager: MT5Manager):
        self.mt5 = mt5_manager

        # Option 1: Keep existing (NO CHANGE)
        self.signal_detector = SignalDetector()

        # Option 2: Add router (OPTIONAL)
        if BREAKOUT_MODULE_ENABLED:
            from strategies.strategy_router import StrategyRouter
            self.router = StrategyRouter()
        else:
            self.signal_detector = SignalDetector()  # Existing behavior
```

**Alternative**: Keep confluence_strategy.py **completely unchanged**, create new `trading_bot_breakout.py` entry point

**Status**: ⚠️  DECISION NEEDED - Modify existing or create new entry point?

---

## Phase 3: Validation (Days 5-6)
**Goal**: Backtest and paper trade BEFORE live

### Day 5: Historical Backtest

**Files**: Already created ✅
- `backtest_lvn_breakout.py` - Validates strategy
- `analyze_by_adx_regime.py` - ADX regime analysis

**Additional Testing**:
```bash
# Test on different market conditions
python backtest_lvn_breakout.py --min-confluence 6
python backtest_lvn_breakout.py --adx-threshold 27
python backtest_lvn_breakout.py --analyze-by-month
```

**Acceptance Criteria**:
- [ ] Win rate >= 55%
- [ ] Avg profit/trade >= $4.00
- [ ] Risk/reward >= 1:1.5
- [ ] Confluence score 6+ preferred

**Status**: ✅ Initial backtest complete (56.8% WR, $5.09 avg)

---

### Day 6: Paper Trading

**Setup**: Run both strategies in demo account simultaneously

**Config** (`breakout_config.py`):
```python
BREAKOUT_MODULE_ENABLED = True
BREAKOUT_PAPER_TRADE_ONLY = True  # Logs signals but doesn't trade
```

**Monitoring**:
```python
# Enhanced logging for both strategies
logger.info(f"🔄 Strategy Router | {symbol} | ADX: {adx:.1f} | Using: {strategy}")
logger.info(f"📊 Reversion Signal | {symbol} | Score: {score}")
logger.info(f"🚀 Breakout Signal | {symbol} | Score: {score}")
```

**Acceptance Criteria**:
- [ ] Both strategies log correctly
- [ ] No conflicts (only ONE active per symbol)
- [ ] Breakout signals only in trending markets (ADX >= 25)
- [ ] Reversion signals only in ranging markets (ADX < 25)
- [ ] Paper trade results match backtest expectations

**Status**: ❌ Not started

---

## Phase 4: Production (Day 7)
**Goal**: Deploy with safety controls

### Safety Controls

**Kill Switches** (`breakout_config.py`):
```python
# Emergency disable
BREAKOUT_MODULE_ENABLED = True  # Can disable instantly

# Performance monitoring
BREAKOUT_MAX_CONSECUTIVE_LOSSES = 3
BREAKOUT_MAX_DAILY_LOSS_PCT = 2.0  # % of account
BREAKOUT_MIN_WIN_RATE_20_TRADES = 45  # Disable if < 45% over 20 trades

# Auto-disable logic
if consecutive_losses >= BREAKOUT_MAX_CONSECUTIVE_LOSSES:
    BREAKOUT_MODULE_ENABLED = False
    logger.critical("⛔ BREAKOUT MODULE AUTO-DISABLED - Max losses reached")
```

**Monitoring Dashboard**:
```python
# Separate performance tracking
breakout_stats = {
    'signals': 0,
    'trades': 0,
    'wins': 0,
    'losses': 0,
    'win_rate': 0,
    'total_pnl': 0,
    'avg_pnl': 0,
}

reversion_stats = {
    # Same structure
}
```

**Status**: ❌ Not started

---

## File Structure Summary

```
trading_bot/
├── strategies/
│   ├── signal_detector.py           ✅ UNCHANGED - mean reversion
│   ├── breakout_detector.py         ❌ NEW - LVN breakout logic
│   ├── strategy_router.py           ❌ NEW - route based on ADX
│   ├── confluence_strategy.py       ⚠️  OPTIONAL CHANGE (or create new entry)
│   └── recovery_manager.py          ✅ SHARED - both strategies use
│
├── indicators/
│   ├── vwap.py                      ✅ SHARED - both use
│   ├── volume_profile.py            ✅ SHARED - both use
│   ├── htf_levels.py                ✅ SHARED - both use
│   ├── adx.py                       ✅ SHARED - both use
│   └── volume_analyzer.py           ❌ NEW - volume expansion
│
├── config/
│   ├── strategy_config.py           ✅ UNCHANGED - reversion config
│   └── breakout_config.py           ❌ NEW - breakout settings
│
└── main.py                          ⚠️  OPTIONAL CHANGE (or create new)

# Analysis/Backtest (Already Created)
├── backtest_lvn_breakout.py         ✅ DONE
├── analyze_by_adx_regime.py         ✅ DONE
└── BREAKOUT_MODULE_DESIGN.md        ✅ DONE
```

**Legend**:
- ✅ No changes needed
- ❌ New file to create
- ⚠️  Optional modification (can create separate entry point instead)

---

## Risk Management

### Separation of Concerns

| Aspect | Mean Reversion | LVN Breakout |
|--------|---------------|--------------|
| **Config File** | strategy_config.py | breakout_config.py |
| **Detector** | signal_detector.py | breakout_detector.py |
| **Market Condition** | ADX < 25 | ADX >= 25 |
| **Risk/Trade** | 1% | 0.75% |
| **Max Exposure** | 5.04 lots | 4.0 lots |
| **Can Disable?** | ✅ (TREND_FILTER_ENABLED) | ✅ (BREAKOUT_MODULE_ENABLED) |
| **Currently Testing?** | ✅ YES - NO CHANGES | ❌ Not yet deployed |

### Independence Guarantee

**CRITICAL**: The two modules are **completely independent**:

1. ✅ Different config files
2. ✅ Different detector classes
3. ✅ Different market conditions (ADX threshold)
4. ✅ Router ensures only ONE active at a time
5. ✅ Can disable breakout module without affecting reversion
6. ✅ Reversion module code **never modified**

---

## Decision Points

### Decision 1: Integration Method

**Option A**: Modify `confluence_strategy.py` to use router
- Pros: Single entry point, cleaner
- Cons: Modifies existing file (low risk but not zero)

**Option B**: Create `trading_bot_dual.py` as new entry point
- Pros: Zero modification to existing code
- Cons: Two entry points to maintain

**Recommendation**: **Option B** for Phase 1-3, then Option A after validation

---

### Decision 2: Paper Trading Duration

**Option A**: 2-3 days paper trading (Day 6-8)
- Pros: More data, safer
- Cons: Slower to production

**Option B**: 1 day paper trading (Day 6)
- Pros: Faster iteration
- Cons: Less validation

**Recommendation**: **Option A** - Safety first, reversion module is already in testing

---

## Current Status

- ✅ **Backtest Complete**: 56.8% WR, $5.09 avg, +1,082% vs reversion
- ✅ **Optimal Confluence**: Score 6+ identified
- ✅ **Design Documented**: BREAKOUT_MODULE_DESIGN.md
- ❌ **Phase 1**: Not started (breakout_detector.py)
- ❌ **Phase 2**: Not started (strategy_router.py)
- ❌ **Phase 3**: Not started (paper trading)
- ❌ **Phase 4**: Not started (production)

---

## Next Immediate Action

**Would you like to proceed with**:

1. ✅ **Start Phase 1**: Create `breakout_detector.py` (I can build it now)
2. 📊 **More Analysis**: Deeper dive into the 44 LVN breakout trades
3. ⚙️ **Config Setup**: Create `breakout_config.py` first
4. 🔧 **Integration Decision**: Decide on Option A vs B for confluence_strategy.py

**Recommendation**: Start with **Option 3** (config setup), then **Option 1** (detector), then test independently before integration.

Your call - what would you like to tackle first?
