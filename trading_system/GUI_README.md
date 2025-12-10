# EA Trading System - GUI Application

Professional graphical user interface for the EA trading system with full parameter management and real-time monitoring.

## Features

### 🎛️ Parameter Management
- **All Parameters Editable**: Grid, Hedge, Recovery, Confluence, Risk settings
- **MT5 Credentials**: Secure password input for broker connection
- **Save/Load Configuration**: Parameters stored locally in `trading_config.json`
- **Reset to Defaults**: One-click restore to EA reverse-engineered settings
- **Input Validation**: Type-safe parameter entry (int, float, text)

### 📊 Real-Time Monitoring
- **Live Statistics Dashboard**:
  - Trading status (Running/Stopped)
  - Open positions count
  - Total P&L and win rate
  - Current drawdown percentage
  - Today's trade count

- **Console Output**:
  - Color-coded log messages (green=success, yellow=warning, red=error)
  - Real-time trade execution feedback
  - Detailed cycle summaries every update interval
  - Strategy phase indicators (Grid/Hedge/Recovery)
  - Strategy adherence checks

### 📈 Comprehensive Feedback

The console provides detailed feedback on every trading cycle:

**Market Conditions**
- Current price and VWAP
- Standard deviation from mean
- Trend strength analysis

**Position Status**
- Active positions by type (Grid/Hedge/Recovery)
- Current P&L in pips
- Strategy phase identification
- Phase-specific status messages

**Confluence Analysis**
- Entry signal detection
- Confluence score (0-8 factors)
- Active confluence factors listed
- Reason for no entry (if applicable)

**Session Statistics**
- Total trades and win rate
- Today's P&L and total P&L
- Current drawdown percentage

**Strategy Adherence**
- Grid level compliance check
- Recovery level limit monitoring
- Drawdown threshold warnings
- Parameter violation alerts

## Quick Start

### 1. Install Dependencies
```bash
cd trading_system
pip install MetaTrader5 pandas numpy tkinter
```

### 2. Configure MT5 Credentials
On first launch, enter your demo account credentials:
- **MT5 Login**: Your MT5 account number
- **MT5 Password**: Your MT5 password
- **MT5 Server**: Your broker's server (e.g., "YourBroker-Demo")

### 3. Review Parameters
All parameters are pre-loaded from EA reverse engineering:
- **Grid**: 10.8 pips spacing, 6 levels max
- **Hedge**: 2.4x overhedge ratio
- **Recovery**: 1.4x multiplier, 5 levels max
- **Confluence**: Minimum 4 factors required
- **Risk**: 10% max drawdown, 5% daily loss limit

### 4. Save Configuration
Click **"Save Configuration"** to store parameters locally. They will persist across sessions.

### 5. Start Trading
Click **▶ Start Trading** to begin. The system will:
- Connect to MT5
- Scan for confluence signals every update interval (default: 60 seconds)
- Display detailed cycle summaries in console
- Automatically manage positions (grid/hedge/recovery)
- Stop at circuit breakers (max drawdown, daily loss limit)

### 6. Monitor Progress
Watch the console for detailed feedback:
```
============================================================
📊 CYCLE SUMMARY - 2025-12-04 14:30:15
============================================================
Current Price: 1.09450 | VWAP: 1.09380
Deviation: 1.2σ from VWAP

🔹 Active Positions: 3
  Grid: 2 | Hedge: 0 | Recovery: 0
  Current P/L: -8.5 pips
  📐 GRID PHASE (Level 2/6)
  Strategy Status: Building grid - averaging down

🔍 No Entry Signal (waiting for 4+ confluence)

📈 Session Statistics:
  Total Trades: 5 | Win Rate: 60.0%
  Today's P/L: $42.50 | Total P&L: $42.50
  Current Drawdown: 2.3%

✓ Strategy Adherence Check:
  ✓ All parameters within configured limits
============================================================
```

## Console Feedback Explained

### Strategy Phases

**INITIAL ENTRY** ✓
- First position opened
- Monitoring for grid triggers
- No averaging yet

**GRID PHASE** 📐
- Multiple positions averaging down
- Shows current level (e.g., Level 3/6)
- Building position at 10.8 pip intervals

**HEDGE PHASE** 🔄
- 2.4x overhedge active
- Opposite direction position opened
- Waiting for price reversal or continuation

**RECOVERY PHASE** ⚠️
- Martingale active (1.4x multiplier)
- Shows recovery level (e.g., Level 2/5)
- Higher risk - position size increasing

### Color Coding

- **🟢 Green (Success)**: Trades closed at profit, successful signals, connections
- **🟡 Yellow (Warning)**: Hedge/Recovery activation, approaching limits
- **🔴 Red (Error)**: Limit violations, connection failures, critical warnings

### Strategy Adherence Checks

The system validates every cycle:
- ✓ Grid levels within MAX_GRID_LEVELS (6)
- ✓ Recovery levels within MAX_RECOVERY_LEVELS (5)
- ✓ Drawdown below MAX_DRAWDOWN_PCT (10%)

Any violations trigger warnings:
- ⚠️ WARNING: Approaching max drawdown limit (10%)
- ⚠️ WARNING: Recovery levels exceed max (adjust configuration)

## Configuration File

Parameters are saved to `trading_config.json`:

```json
{
    "grid_spacing_pips": 10.8,
    "max_grid_levels": 6,
    "grid_lot_size": 0.01,
    "hedge_ratio": 2.4,
    "hedge_trigger_pips": 30,
    "martingale_multiplier": 1.4,
    "max_recovery_levels": 5,
    "min_confluence_score": 4,
    "max_drawdown_pct": 10.0,
    "daily_loss_limit_pct": 5.0,
    "mt5_login": "12345678",
    "mt5_password": "your_password",
    "mt5_server": "YourBroker-Demo"
}
```

## Running the GUI

### Launch Application
```bash
python gui_trader.py
```

### Alternative: Command Line Version
For headless operation, use the original CLI:
```bash
python demo_trader.py
```

## Safety Features

### Risk Management
- **Max Drawdown Circuit Breaker**: Stops trading at 10% account loss
- **Daily Loss Limit**: Halts trading after 5% daily loss
- **Consecutive Loss Limit**: Stops after 5 consecutive losing trades
- **Position Limits**: Maximum positions per symbol enforced

### Trading Controls
- **Start/Stop Buttons**: Immediate control over trading
- **Clean Shutdown**: Properly closes MT5 connection on exit
- **Active Trading Warning**: Confirms before quitting with open positions

### Parameter Validation
- Type checking (int/float/text)
- Range validation
- Required field checking
- Safe password storage

## Troubleshooting

### MT5 Connection Failed
- Verify MT5 is installed and running
- Check login credentials
- Confirm server name matches broker
- Ensure MetaTrader5 Python package is installed

### No Entry Signals
- Check confluence score (need 4+ factors)
- Verify trending vs ranging market filter
- Review VWAP deviation requirements
- Check previous day level availability

### Console Not Updating
- Verify "Auto-scroll" is checked
- Check update interval setting (default: 60 seconds)
- Ensure trading status shows "🟢 RUNNING"

### Parameter Changes Not Saving
- Click "Save Configuration" after changes
- Check file permissions for `trading_config.json`
- Verify no syntax errors in parameter values

## Performance Tips

1. **Update Interval**: 60 seconds recommended for M15 timeframe
2. **Console Clearing**: Clear console periodically for better performance
3. **Statistics Reset**: Stats accumulate per session (restart to reset)
4. **Multi-Symbol**: Currently uses first symbol only (EURUSD default)

## Strategy Modifications

The GUI makes it easy to test different configurations:

**Conservative** (Recommended for Demo)
- Max Grid Levels: 3
- Max Recovery Levels: 3
- Hedge Ratio: 2.4x
- Max Drawdown: 5%

**Moderate** (EA Default)
- Max Grid Levels: 6
- Max Recovery Levels: 5
- Hedge Ratio: 2.4x
- Max Drawdown: 10%

**Aggressive** (High Risk)
- Max Grid Levels: 6
- Max Recovery Levels: 10
- Hedge Ratio: 3.0x
- Max Drawdown: 15%

## Support

For issues or questions:
- Review console output for detailed error messages
- Check `trading_system.log` for complete logs
- Verify all EA reverse-engineered parameters
- Test with demo account first

## Architecture

The GUI integrates with the trading system:
```
gui_trader.py
  ├─> trade_manager.py (orchestrates trading)
  ├─> confluence_analyzer.py (entry signals)
  ├─> position_managers.py (grid/hedge/recovery)
  ├─> risk_manager.py (safety controls)
  └─> trading_config.py (parameters)
```

Log callbacks flow from TradeManager → GUI console for real-time feedback.

---

**⚠️ IMPORTANT**: This system is for demo account testing only. Always test thoroughly before considering live trading.
