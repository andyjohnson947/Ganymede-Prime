# Trading System - EA Reverse Engineered Strategy

Complete Python trading system implementing the strategy discovered through EA reverse engineering.

## 🎯 Strategy Overview

**Name:** VWAP + Previous Day Level Mean Reversion with Grid/Hedge/Recovery

**Core Strategy:**
- Entry: VWAP Band 1/2 + Previous Day institutional levels + High confluence (4+ factors)
- Market Filter: Ranging markets only (avoids trends >1%)
- Position Management: Grid → Overhedge (2.4x) → Recovery (5 levels max)
- Exit: Mean reversion to VWAP or averaged breakeven

## 📁 System Components

### 1. `trading_config.py`
All configuration parameters discovered from EA reverse engineering:
- Grid: 10.8 pips spacing, 6 levels max, fixed lots
- Hedge: 2.4x ratio, triggers at 30 pips underwater
- Recovery: 5 levels max, 1.4x multiplier
- Risk: 10% max drawdown, 5% daily loss limit

### 2. `confluence_analyzer.py`
Real-time confluence detection:
- VWAP bands calculation (1σ, 2σ, 3σ)
- Previous day levels (POC, VAH, VAL, VWAP, LVN)
- Current volume profile
- Swing high/low detection
- Trend filter (ranging markets only)

### 3. `position_managers.py`
Position management classes:
- `GridManager`: Handles 6-level grid averaging
- `HedgeManager`: 2.4x overhedge management
- `RecoveryManager`: Martingale recovery (5 levels)

### 4. `risk_manager.py`
Risk controls and circuit breakers:
- Max drawdown monitoring (10%)
- Daily loss limits (5%)
- Consecutive loss tracking
- Position limits
- Time filters

### 5. `trade_manager.py`
Main orchestrator:
- MT5 connection and order execution
- Entry signal detection
- Position monitoring
- Automated management

### 6. `demo_trader.py`
Demo testing application:
- Easy-to-use interface
- Real-time monitoring
- Statistics tracking

## 🚀 Quick Start

### Prerequisites

```bash
pip install MetaTrader5 pandas numpy
```

### Setup

1. **Configure MT5 Credentials:**
   ```bash
   cd ..
   python EASY_START.py
   # Choose option 5: Setup MT5 Credentials
   ```

2. **Review Configuration:**
   Edit `trading_config.py` if needed (defaults are from EA reverse engineering)

3. **Run Demo Trader:**
   ```bash
   cd trading_system
   python demo_trader.py
   ```

## 📊 How It Works

### Entry Process

1. **Every minute (configurable):**
   - Fetch latest market data
   - Calculate previous day levels
   - Calculate VWAP bands
   - Check volume profile
   - Detect swing levels

2. **Confluence Analysis:**
   - Score each factor (0-8 points)
   - Require minimum 4 factors
   - Determine direction (buy/sell based on VWAP)

3. **Risk Checks:**
   - Trending market? → Skip
   - Drawdown too high? → Skip
   - Outside trading hours? → Skip
   - Position limits? → Skip

4. **Execute Entry:**
   - If all checks pass → Open initial position

### Position Management

**Once a position is open, the system automatically:**

**Phase 1 - Grid (Levels 1-6):**
- Every 10.8 pips against position
- Add fixed 0.01 lot
- Maximum 6 grid levels

**Phase 2 - Hedge:**
- If 30 pips underwater
- Open opposite position at 2.4x size
- Profits from continued adverse movement

**Phase 3 - Recovery (Levels 7-11):**
- If grid exhausted and still losing
- Add positions with 1.4x multiplier
- Maximum 5 recovery levels

**Exit:**
- When total position is profitable
- Or when price returns to VWAP

## ⚙️ Configuration Options

### Conservative Settings (Default)
```python
MAX_GRID_LEVELS = 6
MAX_RECOVERY_LEVELS = 5
HEDGE_RATIO = 2.4
MAX_DRAWDOWN_PCT = 10.0
MIN_CONFLUENCE_SCORE = 4
```

### Aggressive Settings (Higher Risk)
```python
MAX_GRID_LEVELS = 6
MAX_RECOVERY_LEVELS = 7  # More recovery
HEDGE_RATIO = 2.4
MAX_DRAWDOWN_PCT = 15.0  # Higher DD tolerance
MIN_CONFLUENCE_SCORE = 3  # Lower entry threshold
```

### Ultra-Conservative Settings
```python
MAX_GRID_LEVELS = 4  # Fewer grid levels
MAX_RECOVERY_LEVELS = 3  # Limited recovery
HEDGE_RATIO = 1.0  # Balanced hedge
MAX_DRAWDOWN_PCT = 5.0  # Tight DD limit
MIN_CONFLUENCE_SCORE = 5  # Higher entry threshold
```

## 📈 Expected Performance

Based on EA reverse engineering data:

**Entry Accuracy:**
- Confluence Score 4-6: 68-73% win rate
- Confluence Score 7-8: 83-88% win rate

**Market Conditions:**
- 100% trades in ranging markets
- 0% trades in trending markets
- 72.6% of entries at VWAP bands
- 85% use previous day levels

**Risk Profile:**
- Maximum exposure: ~0.40 lots (with 5 recovery levels)
- vs Original EA: ~4.5 lots (91% reduction)

## 🔍 Monitoring

### Real-Time Status

The demo trader displays:
```
TRADE MANAGER STATUS
================================================================================
Symbol: EURUSD
MT5 Connected: ✅
Open Positions: 7

Risk Status:
  trading_enabled: True
  circuit_breaker: False
  current_balance: 10250.50
  peak_balance: 10300.00
  drawdown_pct: 0.48%
  daily_profit: 250.50
  daily_profit_pct: 2.51%
  consecutive_losses: 0

Open Positions:
  Position(12345, BUY, 0.01, @ 1.16000, OPEN) (initial L0)
  Position(12346, BUY, 0.01, @ 1.15892, OPEN) (grid L1)
  Position(12347, BUY, 0.01, @ 1.15784, OPEN) (grid L2)
  ...
```

### Logs

All activity logged to `trading_system.log`:
- Entry signals with confluence scores
- Position openings/closings
- Risk warnings
- Errors and issues

## 🛡️ Safety Features

### Circuit Breakers

1. **Max Drawdown (10%)**
   - Stops all trading if drawdown exceeds limit
   - Requires manual restart

2. **Daily Loss Limit (5%)**
   - Stops trading for the day
   - Resets next trading day

3. **Consecutive Losses (5)**
   - Pauses trading after 5 losses
   - Prevents cascade failures

4. **Position Limits**
   - Max 20 positions per symbol
   - Max 50 total positions
   - Max 1.0 lot total exposure

### Time Filters

- Avoids hours 0 and 23 (low liquidity)
- Trading window: 01:00 - 23:00 UTC
- Respects preferred sessions

## 🐛 Troubleshooting

### "MT5 initialization failed"
- Ensure MT5 terminal is running
- Check MT5 is enabled for automated trading

### "MT5 login failed"
- Verify credentials in config/mt5_credentials.yaml
- Ensure demo account is active
- Check server name is correct

### "Failed to get market data"
- Check symbol is available on your broker
- Verify internet connection
- Ensure MT5 terminal is connected

### "Trading disabled: Trending market detected"
- System working correctly - EA only trades ranging markets
- Wait for market conditions to change

## 📝 Testing Recommendations

### Phase 1: Paper Trading (Week 1)
- Set `PAPER_TRADING = True` in config
- Monitor for 1 week
- Verify confluence detection works
- Check position management logic

### Phase 2: Micro Lots (Week 2-3)
- Set `GRID_BASE_LOT_SIZE = 0.01`
- Run on demo account
- Monitor drawdowns
- Fine-tune parameters

### Phase 3: Standard Lots (Week 4+)
- Increase lot sizes gradually
- Monitor performance metrics
- Compare with original EA results

## ⚠️ Important Notes

1. **Demo Account Only (Initial Testing)**
   - Test thoroughly before live trading
   - Verify all parameters
   - Monitor for at least 2 weeks

2. **Broker Requirements**
   - MT5 platform
   - Hedging allowed
   - Low spreads (< 2 pips)
   - Reliable execution

3. **Risk Disclaimer**
   - Trading involves risk
   - This system replicates EA behavior
   - Past performance ≠ future results
   - Use proper risk management

## 📚 Further Reading

- `GRID_AND_HEDGE_STRATEGY_CONFIRMED.md` - Strategy analysis
- `HEDGE_AND_RECOVERY_ANALYSIS.md` - Position management details
- `PYTHON_PLATFORM_PARAMETERS.md` - Parameter reference
- `SINGLE_VS_MULTIPLE_STRATEGY_ANALYSIS.md` - Strategy verification

## 🤝 Support

For issues or questions:
1. Check the logs: `trading_system.log`
2. Review configuration: `trading_config.py`
3. Test individual components
4. Verify MT5 connection

---

*Trading system built from EA reverse engineering - 2025-12-03*
