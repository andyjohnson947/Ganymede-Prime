# Backtesting Quick Start Guide

## What is it?

A custom backtesting framework that runs your **exact production strategy code** on historical data to measure performance before risking real money.

## Fastest Way to Start

```bash
# Backtest last 30 days
python backtest.py --symbols EURUSD GBPUSD --days 30 --source mt5

# With full reports
python backtest.py --symbols EURUSD GBPUSD --days 30 --source mt5 \
    --report results.txt \
    --trades trades.csv \
    --equity equity.csv
```

## What Gets Tested?

✅ **Production ConfluenceStrategy** with ALL features:
- Bidirectional routing (Mean Reversion ⟷ Breakout)
- Market regime detection (ADX + Hurst exponent)
- Recovery stack management (Grid + Hedge + DCA)
- Symbol blacklisting on trending markets
- Complete confluence scoring system
- All indicators and filters

✅ **Realistic Simulation**:
- Spread modeling (default 1.0 pips)
- TP/SL execution
- Position tracking
- Multiple timeframes (H1, D1, W1)

## Output Metrics

### Performance
- Net Profit & Return %
- Win Rate
- Profit Factor
- Max Drawdown
- Sharpe/Sortino/Calmar Ratios

### Breakdowns
- Performance by Symbol
- Performance by Strategy (MR vs BO vs Recovery)
- Performance by Day of Week
- Performance by Hour
- Trade duration analysis

### Risk Analysis
- Drawdown periods
- Consecutive wins/losses
- Equity curve

## Command Line Options

```bash
# Basic options
--symbols EURUSD GBPUSD    # Symbols to test
--days 30                   # Test last N days
--start 2024-01-01         # Or specify start date
--end 2024-12-31           # And end date
--source mt5               # Data source (mt5 or csv)

# Trading parameters
--balance 10000            # Initial balance
--spread 1.0               # Spread in pips
--interval 1               # Check interval (hours)

# Output
--report file.txt          # Save detailed report
--trades trades.csv        # Export all trades
--equity equity.csv        # Export equity curve
--quiet                    # Suppress logging
```

## Example: Test Last 3 Months

```bash
python backtest.py \
    --symbols EURUSD GBPUSD USDJPY \
    --days 90 \
    --source mt5 \
    --balance 50000 \
    --spread 1.5 \
    --report 90day_report.txt \
    --trades 90day_trades.csv \
    --equity 90day_equity.csv
```

## Example: Python Script

```python
from datetime import datetime, timedelta
from trading_bot.backtesting import Backtester, PerformanceAnalyzer

# Setup
backtester = Backtester(
    initial_balance=10000.0,
    spread_pips=1.0,
    symbols=['EURUSD', 'GBPUSD']
)

# Load 30 days of data
end_date = datetime.now()
start_date = end_date - timedelta(days=30)
backtester.load_all_data('mt5', start_date, end_date)

# Run
backtester.run(check_interval_hours=1)

# Analyze
results = backtester.get_results()
analyzer = PerformanceAnalyzer(results)

# Print summary
backtester.print_summary()

# Export
analyzer.generate_report('report.txt')
analyzer.export_trades_to_csv('trades.csv')
```

## Interpreting Results

### ✅ Good Signs
- Win Rate > 60%
- Profit Factor > 2.0
- Sharpe Ratio > 1.5
- Max Drawdown < 20%
- Return > 10% per month

### ⚠️ Warning Signs
- Win Rate < 50%
- Profit Factor < 1.5
- Sharpe Ratio < 1.0
- Max Drawdown > 30%
- Long consecutive losses (> 5)

### Strategy Balance
- **Mean Reversion**: Higher win rate (65-75%), smaller profits
- **Breakout**: Lower win rate (40-50%), larger profits
- **Recovery**: Should minimize losses (ideally $0)

## Using CSV Data

If you don't have MT5 or want to use pre-downloaded data:

```bash
# 1. Prepare CSV files
mkdir data
# Add files: data/EURUSD_H1.csv, data/EURUSD_D1.csv, etc.

# 2. Run backtest
python backtest.py --symbols EURUSD --days 30 \
    --source csv \
    --data-dir ./data
```

**CSV Format Required:**
```csv
time,open,high,low,close,tick_volume
2024-01-01 00:00:00,1.10450,1.10485,1.10420,1.10455,1250
2024-01-01 01:00:00,1.10455,1.10490,1.10445,1.10470,1180
...
```

## Optimization Workflow

1. **Initial Test**: Run backtest on recent data (30-90 days)
2. **Review Metrics**: Check win rate, profit factor, drawdown
3. **Identify Issues**: Look at losing trades, drawdown periods
4. **Adjust Config**: Modify `config/strategy_config.py` settings
5. **Re-test**: Run backtest again with new settings
6. **Compare**: Use multiple reports to compare performance
7. **Forward Test**: Test on different time periods
8. **Paper Trade**: Live testing with fake money

## Example Files

Run the example script:
```bash
python examples/backtest_example.py
```

Generates:
- `backtest_report.txt` - Detailed performance report
- `backtest_trades.csv` - All trades with profit/loss
- `backtest_equity.csv` - Equity curve over time

## Key Config Parameters to Test

From `config/strategy_config.py`:

```python
# Confluence scoring
MIN_CONFLUENCE_SCORE = 4  # Try: 3, 4, 5, 6

# Trend filter
ADX_THRESHOLD = 25        # Try: 20, 25, 30
ALLOW_WEAK_TRENDS = True  # Try: True, False

# Recovery stacks
MAX_GRID_LEVELS = 3       # Try: 2, 3, 4
GRID_MULTIPLIER = 1.5     # Try: 1.3, 1.5, 2.0
```

## Troubleshooting

**"No data loaded"**
- Check MT5 is running and logged in
- Verify symbols are correct (EURUSD not EUR/USD)
- Ensure date range has data

**"Strategy error"**
- Check logs in `logs/` directory
- Verify all config files are valid
- Ensure indicators are working

**Poor performance**
- Test different time periods (bull vs bear markets)
- Adjust confluence scoring thresholds
- Review trend filter settings

## Next Steps

1. ✅ Run initial backtest (30 days)
2. 📊 Review performance metrics
3. 🔧 Optimize parameters
4. 📈 Test on different periods
5. 🧪 Paper trade with best settings
6. 💰 Go live (only after consistent success)

## More Info

- Full documentation: `trading_bot/backtesting/README.md`
- Example script: `examples/backtest_example.py`
- Main codebase: `trading_bot/strategies/confluence_strategy.py`

---

**Remember**: Past performance doesn't guarantee future results. Always paper trade before going live!
