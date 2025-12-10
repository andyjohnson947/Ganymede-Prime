# 🔍 EA Reverse Engineering Guide

## What is EA Mining?

EA Mining allows you to:
1. **Monitor** an existing EA running on your MT5 account
2. **Analyze** its trading behavior and strategy
3. **Learn** the EA's decision-making using machine learning
4. **Enhance** the strategy with improvements
5. **Compare** original EA vs enhanced performance

## Quick Start

```bash
# Run the EA mining system
python run.py --mine-ea

# Or use the example directly
python examples/ea_reverse_engineering.py
```

## How It Works

### 1. EA Monitor 📊

The EA Monitor watches your MT5 account and tracks all trades:

```python
from src.ea_mining import EAMonitor

ea_monitor = EAMonitor(mt5_manager, storage)

# Monitor all trades
ea_monitor.start_monitoring()

# Or monitor specific EA by magic number
ea_monitor.start_monitoring(magic_number=12345)

# Get statistics
stats = ea_monitor.get_ea_statistics()
```

**What it captures:**
- Entry/exit prices and times
- Position sizes
- Stop loss and take profit levels
- Profits/losses
- Market conditions at each trade
- Trade duration

### 2. EA Analyzer 🔬

The Analyzer reverse engineers the EA's strategy:

```python
from src.ea_mining import EAAnalyzer

ea_analyzer = EAAnalyzer(ea_monitor)

# Analyze entry patterns
entry_patterns = ea_analyzer.analyze_entry_patterns()

# Detect strategy rules
detected_rules = ea_analyzer.detect_strategy_rules()

# Find weaknesses
weaknesses = ea_analyzer.find_weaknesses()

# Get full report
report = ea_analyzer.generate_full_report()
```

**What it discovers:**
- When the EA prefers to trade (time patterns)
- Buy vs sell preferences
- Indicator-based decision rules
- Win rate and profit patterns
- Weaknesses and losing patterns
- Improvement opportunities

### 3. EA Learner 🤖

Machine learning model that learns the EA's behavior:

```python
from src.ea_mining import EALearner
from src.ml import FeatureEngineer

feature_engineer = FeatureEngineer(ml_config)
ea_learner = EALearner(ea_monitor, feature_engineer)

# Train models to learn EA behavior
results = ea_learner.train(price_data)

# Predict what EA would do now
prediction = ea_learner.predict(current_data)
```

**What it learns:**
- When the EA decides to enter trades
- How it chooses direction (buy vs sell)
- When it exits trades
- Most important factors in EA's decisions

**Models trained:**
- Entry Model: Predicts when EA will trade
- Direction Model: Predicts buy vs sell
- Exit Model: Predicts when EA will close

### 4. Strategy Enhancer ⚡

Creates an improved version of the EA:

```python
from src.ea_mining import StrategyEnhancer

enhancer = StrategyEnhancer(ea_monitor, ea_analyzer, ea_learner)

# Analyze and create enhancements
enhancements = enhancer.analyze_and_create_enhancements()

# Generate enhanced signal
enhanced_signal = enhancer.generate_enhanced_signal(
    current_data,
    ea_prediction
)

# Backtest enhanced vs original
comparison = enhancer.backtest_enhancements(historical_data)
```

**Enhancements created:**
- **Time filters**: Avoid trading during losing hours
- **Circuit breakers**: Stop after consecutive losses
- **Risk management**: Adjust stop loss/take profit
- **Confirmation filters**: Require alignment of key factors
- **Exit improvements**: Better timing for closing trades

## Example Output

```
=== EA Statistics ===
Total Trades:    127
Win Rate:        58.3%
Total Profit:    $1,245.50
Profit Factor:   1.82

=== Detected Strategy Rules ===
1. Buys when RSI_14 is LOW (avg: 32.4) [confidence: 87%]
2. Trades mostly during hour 9:00 [confidence: 70%]
3. Uses fixed lot size: ~0.10 [confidence: 90%]

=== Identified Weaknesses ===
1. [HIGH] Win rate is only 45.2%
2. [HIGH] Average loss ($45.20) is much larger than average win ($28.50)
3. [MEDIUM] Maximum losing streak: 7 trades
4. [LOW] Losing money at hour 23:00 ($-124.50 over 8 trades)

=== Improvement Opportunities ===
1. Improve entry timing to increase win rate
2. Tighten stop losses or widen take profits
3. Add circuit breaker to stop trading after consecutive losses
4. Avoid trading during consistently losing hours

=== ML Learning Results ===
Entry Model Accuracy: 78.5%

Top factors EA uses to decide when to trade:
  1. slope_20: 0.089
  2. slope_roc_10: 0.073
  3. volume_roc_20: 0.062
  4. RSI_14: 0.059
  5. slope_acceleration_10: 0.054

=== Strategy Enhancements ===

Filters:
  1. Don't trade during hour 23:00
  2. Stop trading after 3 consecutive losses

Risk Management:
  1. Reduce stop loss by 25%
  2. Increase take profit by 50%

Entry Improvements:
  1. Require alignment of top 3 factors

=== Performance Comparison ===

Original EA:
  Total Trades: 127
  Win Rate:     58.3%
  Total Profit: $1,245.50

Enhanced Strategy:
  Total Trades: 103
  Win Rate:     64.1%
  Total Profit: $1,584.30

Improvement:
  Profit Change: $338.80 (+27.2%)
  Win Rate Change: +5.8%
  Trades Filtered Out: 24
```

## Use Cases

### Use Case 1: Bought a Black Box EA

You bought an EA but don't know how it works:

```bash
python run.py --mine-ea
```

**Results:**
- Understand the EA's logic
- Identify weaknesses
- Create improved version
- Verify vendor claims

### Use Case 2: Your Own EA Needs Improvement

You wrote an EA that's not performing well:

```bash
python run.py --mine-ea
```

**Results:**
- Find specific weaknesses
- Get concrete improvement suggestions
- ML identifies what works/doesn't work
- Backtest improvements

### Use Case 3: Combine Multiple EAs

Run multiple EAs and analyze them:

```python
# Monitor EA 1
ea1_monitor = EAMonitor(mt5, storage)
ea1_monitor.start_monitoring(magic_number=111)

# Monitor EA 2
ea2_monitor = EAMonitor(mt5, storage)
ea2_monitor.start_monitoring(magic_number=222)

# Analyze both and combine strengths
```

### Use Case 4: Daily EA Monitoring

Run continuously to track EA performance:

```python
# Real-time monitoring
while True:
    new_trades = ea_monitor.update(current_data)

    for trade in new_trades:
        # Log trade
        # Check if EA is deviating from learned behavior
        # Alert on anomalies

    time.sleep(300)  # Check every 5 minutes
```

## Important Notes

### What Gets Analyzed

✅ **Captured:**
- All trades (entries/exits)
- Market conditions at entry
- Technical indicators at entry
- Time patterns
- Position sizing
- Stop loss/take profit usage
- Trade outcomes

❌ **Not Captured:**
- EA's internal logic (source code)
- Why specific values were chosen
- EA's comments or labels

### Accuracy

The ML models learn from:
- Historical trades (what the EA did)
- Market conditions (when it did it)

**Accuracy depends on:**
- Number of trades (more = better)
- Consistency of EA behavior
- Quality of market data
- Number of symbols traded

**Typical accuracy:**
- 70-85% for entry timing
- 75-90% for direction
- 60-75% for exit timing

### Limitations

1. **Black box EAs**: Can only learn from observable behavior
2. **Adaptive EAs**: If EA changes strategy, need to retrain
3. **Small sample**: Need at least 50+ trades for good results
4. **Multiple strategies**: If EA uses multiple strategies, may average them

## Advanced Usage

### Custom Analysis

```python
# Get all EA trades as DataFrame
trades_df = ea_monitor.get_trades_dataframe()

# Custom analysis
import matplotlib.pyplot as plt

# Plot equity curve
trades_df['cumulative_profit'] = trades_df['profit'].cumsum()
trades_df['cumulative_profit'].plot()
plt.show()

# Analyze by day of week
by_day = trades_df.groupby('day_of_week')['profit'].mean()
print(by_day)
```

### Integration with Your Bot

```python
# Run enhanced strategy live
while True:
    # Get current market data
    current_data = get_market_data()

    # Get EA prediction
    ea_prediction = ea_learner.predict(current_data)

    # Apply enhancements
    enhanced_signal = enhancer.generate_enhanced_signal(
        current_data,
        ea_prediction
    )

    # Execute if signal is strong
    if enhanced_signal['enhanced_signal']['should_trade']:
        execute_trade(enhanced_signal)
```

## Troubleshooting

**No trades found:**
- Make sure EA is running on MT5
- Check magic_number filter
- Verify MT5 connection
- Check date range

**Low accuracy:**
- Collect more trades (50+ recommended)
- Ensure EA behavior is consistent
- Check if EA is adaptive (changes over time)
- Verify market data quality

**Enhancement doesn't improve:**
- EA might already be optimal
- Need more data for learning
- Try different enhancement strategies
- Backtest on longer period

## Next Steps

1. **Monitor**: Let EA run and collect data
2. **Analyze**: Run EA mining after 50+ trades
3. **Learn**: Train ML models on EA behavior
4. **Enhance**: Apply suggested improvements
5. **Paper Trade**: Test enhanced strategy
6. **Live**: Deploy if improvements are significant

---

**Remember**: This tool learns from EA behavior, not its source code. The more trades you have, the better it learns! 🎯
