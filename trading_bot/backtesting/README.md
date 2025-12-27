# Backtesting Framework

Custom backtesting framework that runs your **exact production strategy code** on historical data.

## Features

- **Production Code Testing**: Uses actual `ConfluenceStrategy` with all features:
  - Bidirectional routing (Mean Reversion ⟷ Breakout)
  - Market regime detection (ADX + Hurst)
  - Recovery stack management (Grid + Hedge + DCA)
  - Symbol blacklisting on trending markets
  - Complete confluence scoring

- **Realistic Simulation**:
  - Accurate spread modeling
  - TP/SL execution
  - Position tracking and P&L calculation
  - Multiple timeframe support (H1, D1, W1)

- **Comprehensive Analysis**:
  - Sharpe, Sortino, Calmar ratios
  - Drawdown analysis
  - Performance by symbol, strategy, day, hour
  - Trade statistics and equity curves

## Quick Start

### 1. Command Line (Easiest)

```bash
# Backtest last 30 days from MT5
python backtest.py --symbols EURUSD GBPUSD --days 30 --source mt5

# Custom date range
python backtest.py --symbols EURUSD --start 2024-01-01 --end 2024-12-31 --source mt5

# With reports and exports
python backtest.py --symbols EURUSD --days 30 \
    --report results.txt \
    --trades trades.csv \
    --equity equity.csv

# Custom parameters
python backtest.py --symbols EURUSD --days 30 \
    --balance 50000 \
    --spread 1.5 \
    --interval 1
```

### 2. Python Script

```python
from datetime import datetime, timedelta
from trading_bot.backtesting import Backtester, PerformanceAnalyzer

# Initialize
backtester = Backtester(
    initial_balance=10000.0,
    spread_pips=1.0,
    symbols=['EURUSD', 'GBPUSD']
)

# Load data from MT5
end_date = datetime.now()
start_date = end_date - timedelta(days=30)
backtester.load_all_data('mt5', start_date, end_date)

# Run backtest
backtester.run(check_interval_hours=1)

# Analyze results
results = backtester.get_results()
analyzer = PerformanceAnalyzer(results)

# Print summary
backtester.print_summary()

# Generate detailed report
report = analyzer.generate_report('report.txt')
print(report)

# Export data
analyzer.export_trades_to_csv('trades.csv')
analyzer.export_equity_curve_to_csv('equity.csv')
```

### 3. CSV Data Source

If you don't have MT5 or want to use pre-downloaded data:

```bash
# Prepare CSV files
# Format: symbol_timeframe.csv (e.g., EURUSD_H1.csv)
# Required columns: time, open, high, low, close, tick_volume

mkdir -p data
# Place your CSV files in data/ directory:
# data/EURUSD_H1.csv
# data/EURUSD_D1.csv
# data/EURUSD_W1.csv
# ... etc

# Run backtest
python backtest.py --symbols EURUSD --days 30 \
    --source csv \
    --data-dir ./data
```

## Output Metrics

### Basic Statistics
- Initial/Final Balance & Equity
- Net Profit & Return %
- Total Trades
- Win Rate
- Profit Factor

### Risk Metrics
- **Sharpe Ratio**: Risk-adjusted return
- **Sortino Ratio**: Downside-risk adjusted return
- **Calmar Ratio**: Return / Max Drawdown
- **Max Drawdown**: Largest peak-to-trough decline
- **Drawdown Duration**: Time to recover from drawdowns

### Trade Analysis
- Consecutive wins/losses
- Performance by symbol
- Performance by strategy (MR vs BO vs Recovery)
- Performance by day of week
- Performance by hour
- Average trade duration

## Example Output

```
================================================================================
BACKTEST SUMMARY
================================================================================

📊 Performance:
   Initial Balance:    $  10,000.00
   Final Balance:      $  12,456.78
   Final Equity:       $  12,456.78
   Net Profit:         $   2,456.78
   Max Drawdown:       $     345.21
   Return:                   24.57%

📈 Trading Activity:
   Total Trades:                 48
   Winning Trades:               32
   Losing Trades:                16
   Win Rate:                  66.67%

💰 Profit Metrics:
   Total Profit:       $   3,567.89
   Total Loss:         $   1,111.11
   Profit Factor:              3.21
   Avg Trade Duration:         8.5 hours

📍 Profit by Symbol:
      EURUSD:       $   1,234.56
      GBPUSD:       $   1,222.22

🎯 Profit by Strategy:
   Mean Reversion:   $   1,890.45
        Breakout:   $     566.33
        Recovery:   $       0.00
```

## Architecture

### MockMT5Manager
Simulates MT5 broker behavior:
- Historical data replay
- Order execution with spread
- TP/SL checking
- Position tracking
- P&L calculation

### Backtester
Main backtesting engine:
- Loads historical data (MT5 or CSV)
- Advances time bar-by-bar
- Runs production `ConfluenceStrategy.run_once()`
- Tracks all events and trades

### PerformanceAnalyzer
Statistical analysis:
- Risk metrics (Sharpe, Sortino, Calmar)
- Drawdown analysis
- Trade pattern analysis
- Performance breakdowns

## Data Requirements

### MT5 Source
- MT5 must be installed and configured
- Access to historical data for symbols
- Requires H1, D1, and W1 timeframes

### CSV Source
CSV files must have these columns:
- `time` - Timestamp (ISO format or Unix timestamp)
- `open` - Open price
- `high` - High price
- `low` - Low price
- `close` - Close price
- `tick_volume` - Volume

Example CSV format:
```csv
time,open,high,low,close,tick_volume
2024-01-01 00:00:00,1.10450,1.10485,1.10420,1.10455,1250
2024-01-01 01:00:00,1.10455,1.10490,1.10445,1.10470,1180
...
```

## Interpreting Results

### Good Performance Indicators
- Win Rate > 60%
- Profit Factor > 2.0
- Sharpe Ratio > 1.5
- Sortino Ratio > 2.0
- Max Drawdown < 20% of balance
- Drawdown recovery < 10 days

### Warning Signs
- Win Rate < 50%
- Profit Factor < 1.5
- Sharpe Ratio < 1.0
- Max Drawdown > 30%
- Long drawdown periods (> 30 days)
- High consecutive losses (> 5)

### Strategy-Specific Analysis
- **Mean Reversion**: Should have higher win rate (65-75%) but smaller avg profit
- **Breakout**: Lower win rate (40-50%) but larger avg profit
- **Recovery**: Should minimize losses (ideally $0 if working perfectly)

## Optimization Tips

1. **Analyze by Hour**: Identify best trading hours
2. **Analyze by Day**: Avoid low-performing days
3. **Symbol Selection**: Focus on profitable symbols
4. **Spread Impact**: Test with realistic spreads (1.0-2.0 pips)
5. **Drawdown Periods**: Identify market conditions causing drawdowns

## Limitations

- **Slippage**: Not modeled (assumes perfect execution)
- **Swap**: Not included in calculations
- **Commission**: Not included
- **Liquidity**: Assumes all orders fill
- **Spread**: Constant spread (real spreads vary)
- **Market Impact**: Not modeled

## Troubleshooting

### "No data loaded"
- Check MT5 connection
- Verify symbols are correct
- Ensure date range has data available

### "Strategy error"
- Check logs for details
- Verify all indicators are working
- Ensure config files are valid

### Low performance
- Adjust `MIN_CONFLUENCE_SCORE` in config
- Review trend filter settings (ADX thresholds)
- Check if market conditions match strategy assumptions

## Next Steps

After backtesting:

1. **Review Results**: Analyze performance metrics
2. **Optimize Parameters**: Adjust confluence weights, ADX thresholds
3. **Test Different Periods**: Bull vs bear markets, different years
4. **Forward Test**: Test on recent data (walk-forward)
5. **Paper Trade**: Live testing with fake money
6. **Live Trading**: Only after consistent paper trading success

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review this README
3. Check main project documentation
