# Scalping Module Documentation

## Overview

The Scalping Module is a high-frequency momentum-based trading strategy designed to complement the existing Confluence Strategy. While the Confluence Strategy focuses on H1 mean reversion with Grid/Hedge/DCA recovery, the Scalping Module targets fast M1/M5 entries with tight stops and quick exits.

## Strategy Characteristics

### Entry Logic
The scalping module uses a **multi-factor confirmation system** requiring a minimum score of 50/100:

**Buy Signals:**
- RSI oversold bounce (20-40 range): +25 points
- Stochastic bullish cross in oversold (<40): +30 points
- Volume spike + bullish candle: +25 points
- Bullish breakout above resistance: +30 points
- Strong bullish momentum candle: +15 points

**Sell Signals:**
- RSI overbought rejection (60-80 range): +25 points
- Stochastic bearish cross in overbought (>60): +30 points
- Volume spike + bearish candle: +25 points
- Bearish breakdown below support: +30 points
- Strong bearish momentum candle: +15 points

### Exit Logic
1. **Take Profit**: 2:1 risk-reward ratio (automatic)
2. **Stop Loss**: Below recent swing low/high + 3 pip buffer (automatic)
3. **Time Exit**: Force close after 10 minutes (configurable)
4. **Trailing Stop**: Moves to breakeven, then trails at 5 pips (optional)

### Key Differences from Confluence Strategy

| Feature | Confluence Strategy | Scalping Strategy |
|---------|-------------------|-------------------|
| Timeframe | H1 (hourly) | M1/M5 (1-5 minutes) |
| Entry Type | Mean reversion | Momentum breakouts |
| Hold Time | Hours (up to 12h) | Minutes (target <5min) |
| Profit Target | 1% account (~$10) | 10-16 pips per trade |
| Stop Loss | None (uses recovery) | Tight 5-8 pips |
| Recovery | Grid/Hedge/DCA | None (straight in/out) |
| Lot Size | 0.05 lots | 0.01 lots |
| Max Positions | 3 total | 3 scalps max |

## Configuration

### Basic Setup

Edit `trading_bot/config/strategy_config.py`:

```python
# Enable scalping module
SCALPING_ENABLED = True  # Set to True to activate

# Scalping timeframe
SCALP_TIMEFRAME = 'M1'  # M1 or M5

# Lot size
SCALP_LOT_SIZE = 0.01  # Start small

# Position limits
SCALP_MAX_POSITIONS = 3
SCALP_MAX_POSITIONS_PER_SYMBOL = 1
```

### Advanced Parameters

```python
# Signal detection
SCALP_MOMENTUM_PERIOD = 14  # RSI/Stochastic period
SCALP_VOLUME_SPIKE_THRESHOLD = 1.5  # Volume multiplier
SCALP_BREAKOUT_LOOKBACK = 20  # Bars for breakout detection
SCALP_BARS_TO_FETCH = 100  # Historical data to analyze

# Exit management
SCALP_MAX_HOLD_MINUTES = 10  # Force close after this time
SCALP_USE_TRAILING_STOP = True  # Enable trailing
SCALP_TRAILING_STOP_PIPS = 5  # Trail distance

# Trading sessions (UTC times)
SCALP_TRADING_SESSIONS = {
    'london': {'start': '08:00', 'end': '12:00', 'enabled': True},
    'new_york': {'start': '13:00', 'end': '17:00', 'enabled': True},
    'overlap': {'start': '13:00', 'end': '16:00', 'enabled': True},
}

# Check interval
SCALP_CHECK_INTERVAL_SECONDS = 10  # Scan frequency
```

## Usage

### Run Both Strategies (Dual Mode)

```bash
# Set SCALPING_ENABLED = True in strategy_config.py, then:
python main.py --login 12345 --password "yourpass" --server "Broker-Server"
```

Both strategies will run in parallel:
- Confluence Strategy on H1 (mean reversion)
- Scalping Strategy on M1 (momentum)

### Run Scalping Only

```bash
python main.py --login 12345 --password "yourpass" --server "Broker-Server" --scalping-only
```

### Disable Scalping (Even if Config Enabled)

```bash
python main.py --login 12345 --password "yourpass" --server "Broker-Server" --no-scalping
```

## Output Examples

### Signal Detection

```
============================================================
🎯 SCALPING SIGNAL DETECTED
============================================================
Symbol: EURUSD
Direction: BUY
Price: 1.08450
Signal Strength: 75/100
Time: 2025-12-15 14:35:22

Entry Reasons:
  ✓ RSI oversold bounce (35.2)
  ✓ Stochastic bullish cross (32.1)
  ✓ Bullish breakout

Stop Loss: 1.08398
Take Profit: 1.08554
Risk: 5.2 pips
Reward: 10.4 pips
R:R Ratio: 1:2.0
============================================================
```

### Trade Execution

```
✅ Scalp opened: Ticket #123456
   Direction: BUY
   SL: 1.08398 | TP: 1.08554
```

### Position Management

```
📍 Moving SL to breakeven for scalp #123456
📍 Trailing SL for scalp #123456: 1.08470
✅ Scalp #123456 closed: +8.5 pips (tp_or_sl)
```

### Statistics

```
============================================================
📊 SCALPING STATISTICS
============================================================
Signals Detected: 45
Trades Opened: 32
Trades Closed: 30
Wins: 21
Losses: 9
Total Pips: 85.5
Win Rate: 70.0%
Average Pips: 2.9
============================================================
```

## Best Practices

### 1. Session Selection

Scalping works best during **high volatility periods**:

✅ **Best Times (UTC):**
- London open: 08:00-12:00
- NY open: 13:00-17:00
- **London/NY overlap: 13:00-16:00** (highest volume)

❌ **Avoid:**
- Asian session (22:00-06:00) - low volatility
- Weekends and major holidays
- News releases (use economic calendar)

### 2. Lot Size Management

Start conservatively:
- **Beginner**: 0.01 lots
- **Intermediate**: 0.02-0.03 lots
- **Advanced**: Up to 0.05 lots

Never risk more than 1% per scalp.

### 3. Symbol Selection

**Best for Scalping:**
- EURUSD (tight spreads, high liquidity)
- GBPUSD (good volatility)
- USDJPY (consistent movement)

**Avoid:**
- Exotic pairs (wide spreads)
- Low liquidity symbols
- Highly correlated pairs simultaneously

### 4. Dual-Strategy Balance

When running both strategies:
- **Confluence**: Larger positions (0.05 lots), longer holds
- **Scalping**: Smaller positions (0.01 lots), quick trades
- Total exposure: Monitor combined lot sizes
- Account balance: Ensure sufficient margin for both

### 5. Performance Monitoring

Track these metrics:
- **Win Rate**: Target 60%+ (scalping is harder)
- **Average Pips**: Should be positive over 20+ trades
- **Max Drawdown**: Keep under 5% of account
- **Sharpe Ratio**: Measure risk-adjusted returns

## Risk Management

### Position Limits

```python
SCALP_MAX_POSITIONS = 3  # Never more than 3 scalps open
SCALP_MAX_POSITIONS_PER_SYMBOL = 1  # One scalp per symbol
```

### Time Limits

```python
SCALP_MAX_HOLD_MINUTES = 10  # Force close stale positions
```

This prevents scalps from becoming unwanted swing trades.

### Stop Loss Rules

- **Always use SL**: Every scalp has automatic SL
- **Never remove SL**: Critical for scalping
- **Trail when profitable**: Move to breakeven ASAP

### Exposure Control

With dual strategies:
- Confluence: Up to 15 lots (with recovery)
- Scalping: Up to 0.03 lots (3 × 0.01)
- **Total**: Monitor combined exposure

## Troubleshooting

### No Signals Detected

**Causes:**
- Outside trading sessions
- Insufficient bars (need 50+ bars)
- Signal score below 50 threshold
- Market too quiet (no volume spikes)

**Solutions:**
- Check `SCALP_TRADING_SESSIONS` enabled
- Lower minimum score (risky)
- Wait for London/NY sessions
- Verify MT5 data feed active

### Too Many Losses

**Causes:**
- Trading during low volatility
- Spreads too wide
- Signal threshold too low
- Wrong timeframe (M1 vs M5)

**Solutions:**
- Only trade during high-volume sessions
- Check broker spreads (should be <2 pips)
- Increase minimum signal score to 60
- Try M5 instead of M1 (less noise)

### Positions Not Closing

**Causes:**
- TP/SL not reached
- Time limit too high
- Trailing stop too tight

**Solutions:**
- Verify `SCALP_MAX_HOLD_MINUTES` setting
- Check if broker executed TP/SL
- Review trailing stop logic
- Manual close if necessary

## Architecture

### Files Created

```
trading_bot/
├── strategies/
│   ├── scalping_signal_detector.py  # Signal detection logic
│   └── scalping_strategy.py         # Main scalping orchestrator
├── config/
│   └── strategy_config.py           # Updated with SCALP_* parameters
└── main.py                          # Updated for dual-strategy mode
```

### Class Hierarchy

```
ScalpingStrategy
├── ScalpingSignalDetector
│   ├── _calculate_rsi()
│   ├── _calculate_stochastic()
│   ├── _detect_volume_spike()
│   ├── _detect_breakout()
│   └── detect_signal()
├── RiskCalculator
└── MT5Manager
```

## Performance Expectations

### Realistic Targets

- **Win Rate**: 60-70%
- **Average Pips**: 3-5 pips per trade
- **Trade Frequency**: 5-15 trades per day
- **Daily P&L**: +10 to +30 pips (good day)

### Account Growth

With 0.01 lots on $1,000 account:
- Win: +$1.00 per pip × 10 pips = +$10
- Loss: -$1.00 per pip × 5 pips = -$5
- Net (70% WR): (0.7 × $10) - (0.3 × $5) = +$5.50 per trade

10 trades/day = **+$55/day** = **+$1,100/month** (5.5% monthly)

**Important**: Past performance doesn't guarantee future results. Always test on demo first.

## Testing Recommendations

### 1. Demo Testing (Mandatory)

Before live trading:
1. Run on demo account for 2 weeks minimum
2. Track all signals and exits
3. Verify win rate >60%
4. Check average pip profit >2 pips
5. Monitor max drawdown <5%

### 2. Backtesting

```python
# Set in strategy_config.py
BACKTEST_MODE = True
BACKTEST_START_DATE = '2024-01-01'
BACKTEST_END_DATE = '2024-12-31'
```

Analyze:
- Win rate by session
- Best trading hours
- Drawdown periods
- Sharpe ratio

### 3. Forward Testing

Once demo successful:
1. Start with $100 live (micro account)
2. Use 0.01 lots only
3. Run for 1 month
4. If profitable, scale gradually

## Integration with Confluence Strategy

### Complementary Strengths

**Confluence Strategy:**
- Catches mean reversion moves
- Holds for hours to capture full reversion
- Uses recovery to manage drawdowns
- Targets $10+ per trade

**Scalping Strategy:**
- Catches momentum breakouts
- Quick in/out (minutes)
- No recovery needed (tight stops)
- Targets $5-10 per trade

### Combined Benefits

1. **Diversification**: Different timeframes and approaches
2. **Consistent Income**: Scalping fills gaps between confluence trades
3. **Risk Balance**: Scalping smaller size balances confluence exposure
4. **Market Coverage**: 24/5 opportunities across both strategies

### Potential Conflicts

⚠️ **Watch for:**
- Opposite positions on same symbol (confluence BUY, scalp SELL)
- Combined exposure exceeding account limits
- Margin calls if both strategies max out simultaneously

**Solutions:**
- Monitor total exposure across both
- Set conservative `SCALP_MAX_POSITIONS = 3`
- Keep scalping lot size small (0.01 vs 0.05)

## Future Enhancements

Potential improvements:
- [ ] Machine learning for signal optimization
- [ ] Multi-timeframe confirmation (M5 + M15)
- [ ] News filter integration
- [ ] Adaptive lot sizing based on volatility
- [ ] Advanced trailing stop algorithms
- [ ] Correlation filters between symbols
- [ ] Performance analytics dashboard

## Support

For issues or questions:
- Check configuration in `strategy_config.py`
- Review logs in `trading_bot.log`
- Verify MT5 connection active
- Test on demo account first

---

**Created**: December 2025
**Version**: 1.0
**Author**: Ganymede-Prime Development Team
**License**: Proprietary
