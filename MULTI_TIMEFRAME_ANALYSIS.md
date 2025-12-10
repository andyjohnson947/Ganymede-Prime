# Multi-Timeframe Analysis Features

This document describes the new multi-timeframe analysis capabilities added to the EA Analysis system.

## Overview

Option 1 in EASY_START.py now includes comprehensive multi-timeframe analysis that extends beyond basic EA reverse engineering to provide deeper market insights.

## Features Included

### 1. Volume Profile Multi-Timeframe Analysis (Hourly/Daily/Weekly)

**Volume Profile Analysis** identifies key price levels based on trading activity. The system calculates comprehensive volume metrics across three timeframes:

- **H1 (Hourly)**: Last 100 bars - for intraday trading decisions
- **D1 (Daily)**: Last 20 days - for swing trading context
- **W1 (Weekly)**: Last 12 weeks - for institutional level analysis

For each timeframe, you get:

#### Core Metrics
- **POC (Point of Control)**: Price level with highest volume - strongest support/resistance
- **VAH/VAL (Value Area High/Low)**: 70% volume concentration zone
- **Volume Weighted StdDev**: Measure of price dispersion weighted by volume

#### Key Level Types
- **LVN Levels (Low Volume Nodes)**: Top 5 lowest volume areas
  - Price moves quickly through these zones (low resistance)
  - Ideal for breakout targets
  - Avoid placing stops at LVN levels

- **HVN Levels (High Volume Nodes)**: Top 5 highest volume areas
  - Strong support/resistance zones
  - Institutional players have positions here
  - Price tends to consolidate or reverse at HVN

- **Total Volume**: Aggregate trading activity

**Use Case**:
- Trade **through** LVN levels (breakouts)
- Trade **at** HVN levels (reversals/bounces)
- POC acts as magnet - price often returns to it

### 2. Session Volatility Correlation with ATR

**ATR (Average True Range)** measures market volatility. This analysis correlates volatility with trading sessions.

Analyzed sessions:
- **Tokyo**: 00:00-09:00 UTC
- **London**: 08:00-17:00 UTC
- **New York**: 13:00-22:00 UTC
- **Sydney**: 22:00-07:00 UTC

For each session:
- Average ATR
- Min/Max ATR range
- Standard deviation
- Volatility ranking
- Sample size

**Use Case**: Trade during high-volatility sessions (typically London/NY overlap) for better price movement, or avoid them for lower-risk trading.

### 3. Previous Week Institutional Levels

Institutional traders reference previous week's levels for decision-making. The system provides comprehensive weekly analysis:

#### Price Levels
- **Open**: Week opening price (often tested during new week)
- **High/Low**: Weekly extremes (key support/resistance)
- **Close**: Week closing price (sentiment indicator)
- **Midpoint**: 50% retracement level (equilibrium)
- **Range**: Weekly volatility measure

#### VWAP Analysis
- **VWAP**: Volume-weighted fair value for the week
- **VWAP Deviation Bands**:
  - ±1σ (Standard Deviation): Normal price range
  - ±2σ: Extended price range (potential reversals)
  - ±3σ: Extreme price range (high probability reversals)

#### Volume Profile
- **POC/VAH/VAL**: Week's volume concentration
- **HVN Levels**: High-volume institutional zones
- **LVN Levels**: Low-volume breakout areas

#### Market Structure
- **Swing Highs/Lows**: Top 5 significant turning points
- **Initial Balance**: Monday's first 2 hours range (sets tone for week)

**Use Case**:
- Previous week high/low = strong S/R for current week
- VWAP shows if price is at premium (above) or discount (below)
- Initial balance breakout often leads to trending week
- Swing points act as magnets for price

### 4. Recovery Success Rate Tracking

Analyzes your EA's **recovery/DCA (Dollar Cost Averaging)** sequences to determine:

- Total recovery sequences executed
- Success vs. failure rate
- Success rate by sequence length (2 trades, 3 trades, etc.)
- Average profit/loss per sequence length
- Volume statistics per recovery level

**Use Case**: Understand which recovery strategies work best. If 2-trade sequences have 80% success but 4+ trade sequences fail, you know to limit recovery depth.

### 5. Time-Based Pattern Correlation

Correlates entry success with:

#### By Hour (0-23)
- Win rate per hour
- Total trades per hour
- Average profit per hour
- Identifies top 5 best trading hours

#### By Day of Week
- Performance Monday through Sunday
- Win rates and profitability by day

#### By Trading Session
- Tokyo, London, New York, Sydney
- Session-specific win rates and P/L

**Use Case**: Only trade during your statistically best hours/days. If your system wins 70% during London session but only 40% during Tokyo, focus on London hours.

## How to Use

### Via EASY_START.py (Recommended)

1. Run `python EASY_START.py`
2. Choose **Option 1: Analyze My EA (Full multi-timeframe analysis)**
3. The system will:
   - First run EA reverse engineering
   - Then automatically run multi-timeframe analysis
   - Generate comprehensive reports

### Standalone Execution

```bash
python analyze_multi_timeframe.py
```

This requires:
- MT5 connection configured
- Historical trade data in database

## Output Files

### 1. multi_timeframe_analysis.json
Complete detailed analysis in JSON format. Contains all raw data and calculations.

### 2. multi_timeframe_summary.csv
Condensed summary in CSV format for easy spreadsheet analysis.

### Console Output
Formatted report printed to terminal with:
- LVN levels for all timeframes
- Session volatility rankings
- Previous week institutional levels
- Recovery success rates by length
- Best trading times (top 5 hours)
- Session-specific performance

## Interpreting the Results

### Volume Profile Levels
```
H1 - Hourly (100 bars):
  POC (Point of Control): 1.08450    <- Highest volume = strongest S/R
  VAH (Value Area High):  1.08520    <- Upper 70% volume boundary
  VAL (Value Area Low):   1.08380    <- Lower 70% volume boundary
  Volume Weighted StdDev: 0.00045    <- Price dispersion measure

  📉 LVN Levels (Low Volume - Breakout Zones):
     1. 1.08390  <- Price moves fast through here
     2. 1.08470
     3. 1.08515
     4. 1.08355
     5. 1.08495

  📈 HVN Levels (High Volume - Support/Resistance):
     1. 1.08450  <- Strong institutional level
     2. 1.08420
     3. 1.08485
     4. 1.08410
     5. 1.08460

  Total Volume: 125,430
```

**Trading Application**:
- Price approaching **LVN**? Expect **quick breakout** through that level
- Price approaching **HVN**? Expect **consolidation or reversal**
- Price at **POC**? Expect **consolidation** (magnet effect)
- Price between **VAH/VAL**? Normal trading range (70% of action)
- Price outside **VAH/VAL**? Unusual - potential reversal zone

### Session Volatility
```
London (Rank #1):
  Avg ATR: 0.00085    <- Most volatile session

Tokyo (Rank #4):
  Avg ATR: 0.00042    <- Least volatile session
```

**Trading Application**:
- Match your strategy to session volatility
- Scalping? Choose London
- Swing trading? Tokyo might be better

### Recovery Success Rates
```
By Sequence Length:
  2 trades: 75.0% (15/20) Avg P/L: $45.50   <- High success, acceptable
  3 trades: 60.0% (12/20) Avg P/L: $12.30   <- Moderate success
  4 trades: 30.0% (3/10)  Avg P/L: -$89.20  <- Poor success, AVOID!
```

**Trading Application**:
- Set max recovery level to 3 (before it becomes unprofitable)
- Monitor real-time sequences
- Exit or hedge when approaching failure threshold

### Best Trading Times
```
1. Hour 14:00 - Win Rate: 78.5% (22 trades, Avg P/L: $67.80)
2. Hour 15:00 - Win Rate: 72.1% (18 trades, Avg P/L: $52.30)
3. Hour 09:00 - Win Rate: 68.9% (15 trades, Avg P/L: $41.20)
```

**Trading Application**:
- Create time filters in your EA
- Only trade during statistically profitable hours
- Avoid hours with <50% win rate

## Integration with Existing Systems

The multi-timeframe analyzer is fully integrated with:

- EA Monitor (EAMonitor)
- EA Analyzer (EAAnalyzer)
- Market Profile Calculator
- Volatility Indicators (ATR)
- Confluence Analyzer

All modules work together seamlessly through the existing architecture.

## Technical Details

### Module Location
```
src/ea_mining/multi_timeframe_analyzer.py
```

### Main Class
```python
from src.ea_mining import MultiTimeframeAnalyzer

analyzer = MultiTimeframeAnalyzer()
report = analyzer.generate_comprehensive_report(
    market_data=df,
    trades_df=trades,
    recovery_patterns=patterns
)
```

### Key Methods

- `calculate_lvn_multi_timeframe()`: LVN analysis across timeframes
- `calculate_session_volatility_atr()`: Session-based ATR correlation
- `calculate_previous_week_levels()`: Weekly institutional levels
- `calculate_recovery_success_rate()`: Recovery pattern tracking
- `analyze_time_based_patterns()`: Time correlation analysis
- `generate_comprehensive_report()`: Full analysis execution
- `print_analysis_summary()`: Formatted console output

## Requirements

- Python 3.8+
- pandas, numpy
- MetaTrader5 (for live data)
- Existing trade history database

## Future Enhancements

Potential additions:
- Monthly timeframe analysis
- Multi-symbol correlation
- Machine learning pattern prediction
- Real-time alert system for confluence zones
- Backtesting integration for time filters

## Support

For issues or questions:
- Check EASY_START.py for correct setup
- Ensure MT5 credentials configured
- Verify trade database exists (data/trading_data.db)
- Review console output for specific errors

---

**Created**: December 2025
**Version**: 1.0
**Part of**: EA Analysis System
