# MT5 Strategy Reversal Bot

A comprehensive Python trading bot for MetaTrader 5 with **EA reverse engineering**, pattern recognition, hypothesis testing, machine learning, dollar cost averaging, and advanced market profile analysis.

## 🚀 Quick Start (One-Click Setup)

**Want to analyze your EA with zero hassle?**

1. Copy this folder to your MT5 computer
2. Double-click `EASY_START.bat` (Windows) or run `python3 EASY_START.py` (Mac/Linux)
3. Choose option 1: "Analyze My EA"
4. Done! ✨

**Full instructions:** See [QUICK_START.md](QUICK_START.md) for the super simple 3-step setup.

---

## Features

- **🔍 EA Reverse Engineering** ⭐ **NEW**: Monitor, analyze, and improve existing EAs
  - Real-time EA trade monitoring
  - Automatic strategy pattern detection
  - ML-based imitation learning
  - Weakness identification and improvement suggestions
  - Performance comparison (original vs enhanced)
  - [Full Guide](EA_MINING_GUIDE.md)
- **MT5 Integration**: Full MetaTrader 5 API connectivity with real-time and historical data
- **Machine Learning**: Random Forest and Gradient Boosting models with advanced feature engineering
  - Rate of Change (ROC) features
  - Slope and slope acceleration (rate of change of slope)
  - Volume/flow features and volume acceleration
  - Automated feature engineering and model training
- **Dollar Cost Averaging (DCA)**: Multiple DCA strategies
  - Fixed amount/size DCA
  - Grid-based DCA
  - Time-based DCA
  - Signal-based DCA
  - Dynamic position sizing
- **Pattern Recognition**: Advanced strategy reversal pattern detection
- **Hypothesis Testing**: Statistical validation of trading signals
- **Market Profile Analysis**: VWAP, VAL, POC, VAH calculations
- **Modular Indicators**: Extensible technical indicator framework
- **Data Management**: Automated data collection with daily profile logging
- **Zipline Integration**: Professional backtesting capabilities
- **Scheduling**: Automated daily tasks and data collection
- **Simple GUI**: Easy MT5 account configuration

## Project Structure

```
EA-Analysis/
├── src/
│   ├── mt5_connection/      # MT5 API integration
│   ├── data/                # Data collection & storage
│   ├── indicators/          # Technical indicators (modular)
│   ├── market_profile/      # Volume profile calculations
│   ├── patterns/            # Pattern recognition engine
│   ├── hypothesis/          # Statistical hypothesis testing
│   ├── dca/                 # Dollar cost averaging strategies
│   ├── ml/                  # Machine learning (Random Forest, Gradient Boosting)
│   ├── ea_mining/           # ⭐ EA reverse engineering & enhancement
│   ├── zipline_integration/ # Zipline backtesting
│   ├── scheduler/           # Task scheduling
│   ├── gui/                 # Account configuration GUI
│   ├── bot.py              # Main bot orchestrator
│   └── main.py             # Main entry point
├── config/                  # Configuration files
├── examples/               # Example scripts
├── data/                    # Data storage
├── models/                  # Trained ML models
├── logs/                    # Log files
└── tests/                   # Unit tests
```

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd EA-Analysis
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure MT5 credentials:
   - Run the GUI: `python src/gui/account_setup.py`
   - Or manually edit `config/mt5_credentials.yaml`

## Usage

### Quick Start

```bash
python src/main.py
```

### GUI Configuration

```bash
python src/gui/account_setup.py
```

### Data Collection Only

```bash
python src/data/collector.py --mode historical
```

### Backtesting with Zipline

```bash
python src/zipline_integration/backtest.py
```

## Configuration

Edit `config/config.yaml` to customize:
- Trading symbols
- Timeframes
- Indicator parameters
- Pattern recognition thresholds
- Scheduling intervals

## Technical Indicators

The bot includes a modular indicator system with:
- Moving Averages (SMA, EMA, WMA)
- RSI, MACD, Stochastic
- Bollinger Bands, ATR
- VWAP and Volume Profile
- Custom indicators (easily extensible)

## Market Profile

- **VWAP**: Volume-Weighted Average Price
- **POC**: Point of Control (highest volume node)
- **VAH**: Value Area High
- **VAL**: Value Area Low

## License

MIT License

## Contributing

Contributions welcome! Please read CONTRIBUTING.md first.
