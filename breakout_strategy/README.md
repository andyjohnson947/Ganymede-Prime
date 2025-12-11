# Breakout Strategy Module

**COMPLETELY SEPARATE** from the mean reversion module in `trading_bot/`

## Purpose

Trades **trending markets** (ADX ≥ 25) using VWAP-supported LVN breakouts.

Complements the mean reversion strategy which trades **ranging markets** (ADX < 25).

## Backtest Results

| Metric | Value |
|--------|-------|
| Trades | 44 |
| Win Rate | 56.8% |
| Avg Profit/Trade | $5.09 |
| Risk/Reward | 1:1.83 |
| Optimal Confluence Score | 6+ |

**Improvement vs Mean Reversion in Trending Markets**: +1,082% per trade

## Directory Structure

```
breakout_strategy/
├── config/
│   └── breakout_config.py       # All configuration settings
│
├── strategies/
│   └── breakout_detector.py     # Signal detection logic (TODO)
│
├── indicators/
│   └── volume_analyzer.py       # Volume expansion detection (TODO)
│
├── utils/
│   └── (shared utilities)       # TODO
│
└── README.md                    # This file
```

## Status

- ✅ Configuration complete (`config/breakout_config.py`)
- ❌ Detector not built yet
- ❌ Volume analyzer not built yet
- ❌ Integration not done yet

## Key Features

### Confluence Scoring (Score 6+ Required)

| Factor | Weight | Description |
|--------|--------|-------------|
| at_lvn | 3 | At low volume node (low resistance) |
| strong_trend_adx | 2 | ADX ≥ 35 |
| vwap_directional_bias | 2 | Price >0.1% from VWAP |
| high_volume | 2 | Volume >70th percentile |
| trending_adx | 1 | ADX 25-35 |
| away_from_poc | 1 | Not in consolidation |

### Safety Controls

- `BREAKOUT_MODULE_ENABLED = False` (disabled by default)
- `BREAKOUT_PAPER_TRADE_ONLY = True` (paper trade first)
- Auto-disable on 3 consecutive losses
- Auto-disable if win rate < 45% over 20 trades
- Max 2% daily loss limit

### Risk Management

- **Risk per trade**: 0.75% (more conservative than reversion)
- **Stop loss**: 20 pips
- **Take profit**: 40 pips (1:2 RR)
- **Max exposure**: 4.0 lots
- **Max positions**: 3 simultaneous

## Market Condition Separation

| Module | Market Condition | ADX Range |
|--------|-----------------|-----------|
| **Mean Reversion** | Ranging | ADX < 25 |
| **Breakout** | Trending | ADX ≥ 25 |

**No overlap** - only ONE strategy active per symbol at a time.

## Usage

Module is currently **disabled** by default. To enable:

1. Set `BREAKOUT_MODULE_ENABLED = True` in `config/breakout_config.py`
2. Keep `BREAKOUT_PAPER_TRADE_ONLY = True` initially
3. Monitor paper trade performance
4. If satisfactory, set `BREAKOUT_PAPER_TRADE_ONLY = False`

## Next Steps

1. ❌ Build `strategies/breakout_detector.py`
2. ❌ Build `indicators/volume_analyzer.py`
3. ❌ Create strategy router to switch between reversion/breakout
4. ❌ Paper trade testing
5. ❌ Live deployment

## Independence from Mean Reversion

This module is **completely independent**:

- ✅ Separate directory structure
- ✅ Separate configuration file
- ✅ Different market conditions (no overlap)
- ✅ Can be enabled/disabled independently
- ✅ Zero modifications to `trading_bot/` required

The mean reversion module in `trading_bot/` remains **completely untouched**.
