# Low-Level Design Document
## Confluence Trading Bot (Ganymede-Prime)

**Version**: 2.0
**Date**: 2025-12-24
**Win Rate**: 64.3% (based on 428 trades analyzed from EA)

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Module Hierarchy](#2-module-hierarchy)
3. [Data Flow Diagrams](#3-data-flow-diagrams)
4. [Core Components](#4-core-components)
5. [Trading Logic Flow](#5-trading-logic-flow)
6. [Recovery Mechanisms](#6-recovery-mechanisms)
7. [Exit Logic](#7-exit-logic)
8. [Key Algorithms](#8-key-algorithms)
9. [Database Schema](#9-database-schema)

---

## 1. System Architecture

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                          │
│  ┌──────────────────┐              ┌──────────────────┐        │
│  │   CLI Interface  │              │   GUI Interface  │        │
│  │   (main.py)      │              │ (trading_gui.py) │        │
│  └────────┬─────────┘              └─────────┬────────┘        │
└───────────┼────────────────────────────────┼──────────────────┘
            │                                │
            └────────────┬───────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                    STRATEGY LAYER                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           ConfluenceStrategy (confluence_strategy.py)    │  │
│  │  • Main orchestration loop                               │  │
│  │  • Position management                                   │  │
│  │  • Signal detection coordination                         │  │
│  └───┬─────────────┬──────────────┬────────────┬────────────┘  │
└──────┼─────────────┼──────────────┼────────────┼───────────────┘
       │             │              │            │
       │             │              │            │
┌──────▼─────┐  ┌───▼──────┐  ┌────▼─────┐  ┌──▼──────────────┐
│  Signal    │  │ Recovery │  │ Partial  │  │  Time Filters   │
│  Detector  │  │ Manager  │  │  Close   │  │ Portfolio Mgr   │
│            │  │          │  │ Manager  │  │                 │
└──────┬─────┘  └────┬─────┘  └────┬─────┘  └──┬──────────────┘
       │             │              │            │
       └─────────────┴──────────────┴────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                    INDICATOR LAYER                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │   VWAP   │  │  Volume  │  │   HTF    │  │  Breakout    │   │
│  │          │  │ Profile  │  │  Levels  │  │  Strategy    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                     BROKER INTERFACE                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              MT5Manager (mt5_manager.py)                 │  │
│  │  • Connection management                                 │  │
│  │  • Order execution                                       │  │
│  │  • Position retrieval                                    │  │
│  │  • Market data fetching                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │   MetaTrader 5   │
              │   (MT5 Terminal) │
              └──────────────────┘
```

---

## 2. Module Hierarchy

### 2.1 Directory Structure

```
trading_bot/
├── main.py                          # Entry point
├── config/
│   └── strategy_config.py           # All configuration parameters
├── core/
│   └── mt5_manager.py               # MT5 API wrapper
├── strategies/
│   ├── confluence_strategy.py       # Main strategy orchestrator
│   ├── signal_detector.py           # Signal detection logic
│   ├── breakout_strategy.py         # Breakout signal detection
│   ├── recovery_manager.py          # Grid/Hedge/DCA management
│   ├── partial_close_manager.py     # Partial close logic
│   └── time_filters.py              # Time-based filters
├── indicators/
│   ├── vwap.py                      # VWAP calculation
│   ├── volume_profile.py            # Volume profile (POC/VAH/VAL)
│   ├── htf_levels.py                # Higher timeframe levels
│   └── adx.py                       # ADX indicator
├── portfolio/
│   ├── portfolio_manager.py         # Trading window management
│   └── instruments_config.py        # Instrument-specific settings
├── utils/
│   ├── timezone_manager.py          # GMT timezone handling
│   ├── risk_calculator.py           # Position sizing & risk
│   ├── trading_calendar.py          # Holiday/weekend checks
│   └── logger.py                    # Logging utility
└── gui/
    └── trading_gui.py               # Tkinter GUI
```

### 2.2 Module Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                           main.py                               │
│  • Initializes MT5Manager                                       │
│  • Creates ConfluenceStrategy                                   │
│  • Starts trading loop                                          │
└────────────┬────────────────────────────────────────────────────┘
             │
             ├──► MT5Manager ────► MetaTrader5 API
             │
             └──► ConfluenceStrategy
                      │
                      ├──► SignalDetector
                      │        ├──► VWAP
                      │        ├──► VolumeProfile
                      │        ├──► HTFLevels
                      │        └──► BreakoutStrategy
                      │
                      ├──► RecoveryManager
                      │        └──► (manages Grid/Hedge/DCA)
                      │
                      ├──► PartialCloseManager
                      │
                      ├──► TimeFilters
                      │
                      ├──► PortfolioManager
                      │        ├──► TimeZoneManager
                      │        └──► TradingCalendar
                      │
                      └──► RiskCalculator
```

---

## 3. Data Flow Diagrams

### 3.1 Main Trading Loop Flow

```
                    START
                      │
                      ▼
        ┌─────────────────────────┐
        │  Connect to MT5         │
        └──────────┬──────────────┘
                   │
                   ▼
        ┌─────────────────────────┐
        │  Fetch Market Data      │◄──────────┐
        │  (H1, D1, W1)           │           │
        └──────────┬──────────────┘           │
                   │                           │
                   ▼                           │
        ┌─────────────────────────┐           │
        │  Calculate Indicators   │           │
        │  • VWAP (±1σ, ±2σ)     │           │
        │  • Volume Profile       │           │
        │  • HTF Levels           │           │
        └──────────┬──────────────┘           │
                   │                           │
                   ▼                           │
        ┌─────────────────────────┐           │
        │  Check Positions        │           │
        └──────────┬──────────────┘           │
                   │                           │
           ┌───────┴────────┐                 │
           │                │                 │
           ▼                ▼                 │
    ┌──────────┐    ┌──────────────┐         │
    │ Manage   │    │ Check for    │         │
    │ Existing │    │ New Signals  │         │
    │Positions │    │              │         │
    └────┬─────┘    └──────┬───────┘         │
         │                 │                  │
         │                 │                  │
         ▼                 ▼                  │
    ┌─────────────────────────────┐          │
    │  Execute Actions            │          │
    │  • Recovery (Grid/Hedge)    │          │
    │  • Partial Close            │          │
    │  • Exit Conditions          │          │
    │  • New Trades               │          │
    └──────────┬──────────────────┘          │
               │                              │
               ▼                              │
    ┌─────────────────────────┐              │
    │  Sleep 60 seconds       │              │
    └──────────┬──────────────┘              │
               │                              │
               └──────────────────────────────┘
```

### 3.2 Signal Detection Flow

```
                Market Data (H1, D1, W1)
                         │
                         ▼
        ┌────────────────────────────────┐
        │  Calculate VWAP Bands          │
        │  • VWAP                        │
        │  • VWAP + 1σ, +2σ             │
        │  • VWAP - 1σ, -2σ             │
        └────────────┬───────────────────┘
                     │
                     ▼
        ┌────────────────────────────────┐
        │  Calculate Volume Profile      │
        │  • POC (Point of Control)      │
        │  • VAH (Value Area High)       │
        │  • VAL (Value Area Low)        │
        └────────────┬───────────────────┘
                     │
                     ▼
        ┌────────────────────────────────┐
        │  Extract HTF Levels            │
        │  • D1 High/Low                 │
        │  • W1 High/Low                 │
        └────────────┬───────────────────┘
                     │
                     ▼
        ┌────────────────────────────────┐
        │  Check Time Filters            │
        │  • Mean Reversion Hours        │
        │  • Breakout Hours              │
        │  • Trading Windows             │
        └────────────┬───────────────────┘
                     │
              ┌──────┴──────┐
              │             │
              ▼             ▼
    ┌─────────────┐   ┌─────────────┐
    │ Mean        │   │ Breakout    │
    │ Reversion   │   │ Detection   │
    │ Detection   │   │             │
    └──────┬──────┘   └──────┬──────┘
           │                 │
           └────────┬────────┘
                    │
                    ▼
        ┌────────────────────────────────┐
        │  Calculate Confluence Score    │
        │  +1: VWAP band touch           │
        │  +1: Volume Profile level      │
        │  +1: HTF level                 │
        │  +2: Double confluence         │
        │  +3: Triple confluence         │
        └────────────┬───────────────────┘
                     │
                     ▼
              ┌──────────────┐
              │ Score >= 4?  │
              └──────┬───────┘
                     │
           ┌─────────┴─────────┐
           │                   │
          YES                 NO
           │                   │
           ▼                   ▼
    ┌──────────────┐    ┌──────────┐
    │ OPEN TRADE   │    │  SKIP    │
    └──────────────┘    └──────────┘
```

### 3.3 Position Management Flow

```
           Existing Positions
                  │
                  ▼
    ┌─────────────────────────────┐
    │  For Each Position          │
    └──────────┬──────────────────┘
               │
        ┌──────┴──────┐
        │             │
    Profitable?   Underwater?
        │             │
       YES           YES
        │             │
        ▼             ▼
┌──────────────┐  ┌──────────────────┐
│Partial Close │  │ Recovery Actions │
│              │  │ • Grid (8 pips)  │
│• 50% @ 50%   │  │ • Hedge (8 pips) │
│• 25% @ 75%   │  │ • DCA (20 pips)  │
│• 25% @ 100%  │  │                  │
└──────┬───────┘  └────────┬─────────┘
       │                   │
       └─────────┬─────────┘
                 │
                 ▼
    ┌─────────────────────────────┐
    │  Check Exit Conditions      │
    │  Priority Order:            │
    │  0. Stack Drawdown (4x)     │
    │  1. Profit Target (0.5%)    │
    │  2. Time Limit (12 hrs)     │
    │  3. VWAP Reversion          │
    └──────────┬──────────────────┘
               │
        ┌──────┴──────┐
        │             │
     Exit?         No Exit
        │             │
        ▼             ▼
    ┌────────┐   ┌────────┐
    │ CLOSE  │   │ HOLD   │
    │ STACK  │   │        │
    └────────┘   └────────┘
```

---

## 4. Core Components

### 4.1 MT5Manager (`core/mt5_manager.py`)

**Purpose**: Interface with MetaTrader 5 terminal

**Key Methods**:
```python
class MT5Manager:
    def initialize(login, password, server) -> bool
        # Connect to MT5 terminal

    def get_positions() -> List[Dict]
        # Fetch all open positions

    def get_symbol_data(symbol, timeframe, bars) -> pd.DataFrame
        # Fetch OHLCV data

    def open_position(symbol, type, volume, sl, tp, comment) -> int
        # Place market order

    def close_position(ticket) -> bool
        # Close position by ticket

    def close_partial_position(ticket, volume) -> bool
        # Close partial volume

    def get_account_info() -> Dict
        # Get account balance, equity, etc.
```

**Data Structures**:
```python
# Position Dict
{
    'ticket': int,           # Position ID
    'symbol': str,           # e.g., "EURUSD"
    'type': int,             # 0=buy, 1=sell
    'volume': float,         # Lot size
    'price_open': float,     # Entry price
    'price_current': float,  # Current price
    'profit': float,         # P&L in dollars
    'time': datetime,        # Open time
    'comment': str           # Order comment
}
```

---

### 4.2 ConfluenceStrategy (`strategies/confluence_strategy.py`)

**Purpose**: Main strategy orchestrator

**Architecture**:
```python
class ConfluenceStrategy:
    def __init__(mt5_manager, test_mode=False):
        self.mt5 = mt5_manager
        self.signal_detector = SignalDetector()
        self.recovery_manager = RecoveryManager()
        self.partial_close_manager = PartialCloseManager()
        self.time_filter = TimeFilters()
        self.portfolio_manager = PortfolioManager()

    def start():
        # Main loop - calls _trading_loop()

    def _trading_loop():
        # 1. Fetch market data
        # 2. Calculate indicators
        # 3. Manage positions
        # 4. Check for signals

    def _manage_positions(symbol):
        # For each position:
        # - Check recovery triggers
        # - Execute recovery actions
        # - Check partial close
        # - Check exit conditions

    def _check_for_signals(symbol):
        # Detect new entry signals
        # Validate confluence score >= 4
        # Check time filters
        # Open new positions
```

**State Management**:
```python
self.market_data_cache = {
    'EURUSD': {
        'h1': pd.DataFrame,  # H1 bars
        'd1': pd.DataFrame,  # D1 bars
        'w1': pd.DataFrame   # W1 bars
    },
    'GBPUSD': { ... }
}

self.stats = {
    'trades_opened': int,
    'trades_closed': int,
    'grid_levels_added': int,
    'hedges_activated': int,
    'dca_levels_added': int
}
```

---

### 4.3 SignalDetector (`strategies/signal_detector.py`)

**Purpose**: Detect mean reversion and breakout signals

**Signal Generation**:
```python
class SignalDetector:
    def detect_signal(h1_data, d1_data, w1_data) -> Dict or None:
        # Calculate indicators
        h1_data = self.vwap.calculate(h1_data)
        h1_data = self.volume_profile.calculate(h1_data)

        # Get latest bar
        latest = h1_data.iloc[-1]
        price = latest['close']

        # Initialize confluence score
        score = 0
        factors = []

        # Check VWAP bands
        if price near VWAP ± 2σ:
            score += 2
            factors.append('VWAP_2SD')
        elif price near VWAP ± 1σ:
            score += 1
            factors.append('VWAP_1SD')

        # Check Volume Profile
        if price near POC/VAH/VAL:
            score += 1
            factors.append('VOLUME_PROFILE')

        # Check HTF levels
        if price near D1/W1 High/Low:
            score += 1
            factors.append('HTF_LEVEL')

        # Check breakout
        breakout_signal = self.breakout.detect_breakout(h1_data)
        if breakout_signal:
            score += breakout_signal['strength']
            factors.append('BREAKOUT')

        # Return if score >= 4
        if score >= 4:
            return {
                'symbol': symbol,
                'type': 'buy' or 'sell',
                'score': score,
                'factors': factors,
                'entry_price': price
            }

        return None
```

**Confluence Factors**:
| Factor | Score | Description |
|--------|-------|-------------|
| VWAP ±2σ | +2 | Price at 2 standard deviations |
| VWAP ±1σ | +1 | Price at 1 standard deviation |
| Volume Profile | +1 | Price at POC/VAH/VAL |
| HTF Level | +1 | Price at D1/W1 High/Low |
| Breakout | +1-3 | Breakout strength |

**Minimum Score**: 4 (configured in `MIN_CONFLUENCE_SCORE`)

---

### 4.4 RecoveryManager (`strategies/recovery_manager.py`)

**Purpose**: Manage Grid, Hedge, and DCA recovery mechanisms

**Position Tracking**:
```python
self.tracked_positions = {
    ticket_123: {
        'ticket': 123,
        'symbol': 'EURUSD',
        'entry_price': 1.1000,
        'type': 'buy',
        'initial_volume': 0.04,
        'total_volume': 0.16,        # After grid/DCA
        'grid_levels': [
            {'price': 1.0992, 'volume': 0.04, 'ticket': 124},
            {'price': 1.0984, 'volume': 0.04, 'ticket': 125}
        ],
        'hedge_tickets': [
            {'type': 'sell', 'volume': 0.20, 'ticket': 126}
        ],
        'dca_levels': [
            {'price': 1.0980, 'volume': 0.08, 'ticket': 127}
        ],
        'max_underwater_pips': 25,
        'recovery_active': True,
        'open_time': datetime
    }
}
```

**Recovery Methods**:

#### Grid Trading
```python
def check_grid_trigger(ticket, current_price, pip_value):
    # Trigger: Every 8 pips underwater
    # Volume: Same as original (0.04)
    # Direction: Same as original
    # Max levels: Based on instrument config

    pips_underwater = calculate_pips(entry, current, type)
    expected_levels = int(pips_underwater / 8)  # GRID_SPACING_PIPS

    if expected_levels > current_grid_levels:
        return {
            'action': 'grid',
            'symbol': symbol,
            'type': position_type,
            'volume': GRID_LOT_SIZE,  # 0.04
            'trigger_pips': pips_underwater
        }
```

#### Hedge Trading
```python
def check_hedge_trigger(ticket, current_price, pip_value):
    # Trigger: 8 pips underwater
    # Volume: 5x original (0.04 × 5 = 0.20)
    # Direction: Opposite to original
    # Max: 1 hedge per position

    if pips_underwater >= 8 and not hedged:
        return {
            'action': 'hedge',
            'symbol': symbol,
            'type': 'sell' if original_type == 'buy' else 'buy',
            'volume': initial_volume * 5.0,  # HEDGE_RATIO
            'trigger_pips': pips_underwater
        }
```

#### DCA (Dollar Cost Averaging)
```python
def check_dca_trigger(ticket, current_price, pip_value):
    # Trigger: Every 20 pips underwater
    # Volume: 2x multiplier (0.04, 0.08, 0.16, 0.32)
    # Direction: Same as original
    # Max levels: 4

    pips_moved = calculate_pips(entry, current, type)
    expected_levels = int(pips_moved / 20)  # DCA_TRIGGER_PIPS

    if expected_levels > current_dca_levels and current_dca_levels < 4:
        level = current_dca_levels + 1
        dca_volume = initial_volume * (2.0 ** level)  # DCA_MULTIPLIER

        return {
            'action': 'dca',
            'symbol': symbol,
            'type': position_type,
            'volume': dca_volume,
            'level': level
        }
```

**Stack Drawdown Protection** (NEW):
```python
def check_stack_drawdown(ticket, mt5_positions, pip_value):
    # Calculate expected profit from original trade
    tp_pips = get_take_profit_settings(symbol)['take_profit_pips']
    expected_profit = tp_pips * pip_value * initial_volume * 100000

    # Calculate drawdown threshold (4x expected profit)
    threshold = -1 * (expected_profit * STACK_DRAWDOWN_MULTIPLIER)

    # Calculate net P&L across entire stack
    net_profit = sum(pos['profit'] for pos in stack)

    # Kill stack if exceeded
    if net_profit <= threshold:
        return True  # Close entire stack
```

---

### 4.5 PartialCloseManager (`strategies/partial_close_manager.py`)

**Purpose**: Progressive profit taking

**Tracking**:
```python
self.partial_closes = {
    ticket_123: {
        'entry_price': 1.1000,
        'tp_price': 1.1040,      # 40 pips TP
        'initial_volume': 0.04,
        'remaining_volume': 0.04,
        'levels_closed': [],
        'position_type': 'buy'
    }
}
```

**Levels**:
```python
PARTIAL_CLOSE_LEVELS = [
    {'percent_to_tp': 50, 'close_percent': 50},  # Close 50% @ halfway
    {'percent_to_tp': 75, 'close_percent': 50},  # Close 25% @ 75%
    {'percent_to_tp': 100, 'close_percent': 100} # Close 25% @ 100%
]
```

**Logic**:
```python
def check_partial_close_levels(ticket, current_price, profit_pips):
    position = self.partial_closes[ticket]

    # Calculate progress to TP
    total_distance = position['tp_price'] - position['entry_price']
    current_distance = current_price - position['entry_price']
    percent_to_tp = (current_distance / total_distance) * 100

    # Check each level
    for level in PARTIAL_CLOSE_LEVELS:
        if percent_to_tp >= level['percent_to_tp']:
            if level not in position['levels_closed']:
                # Calculate volume to close
                close_vol = remaining * (level['close_percent'] / 100)

                # If close_vol >= remaining, close full position instead
                if close_vol >= remaining:
                    return 'CLOSE_FULL'

                return {
                    'close_volume': close_vol,
                    'close_percent': level['close_percent'],
                    'level_percent': level['percent_to_tp']
                }
```

**Applies To**:
- ✅ Original positions (when profitable)
- ✅ Grid entries (when profitable)
- ✅ DCA positions (when profitable)
- ❌ Hedge positions (managed separately)

---

## 5. Trading Logic Flow

### 5.1 Entry Logic

```python
# Sequence Diagram for Trade Entry
┌──────────┐     ┌──────────────┐     ┌────────────┐     ┌──────────┐
│ Strategy │     │SignalDetector│     │TimeFilters │     │MT5Manager│
└────┬─────┘     └──────┬───────┘     └─────┬──────┘     └────┬─────┘
     │                  │                    │                 │
     │ detect_signal()  │                    │                 │
     ├─────────────────►│                    │                 │
     │                  │                    │                 │
     │                  │ Calculate VWAP     │                 │
     │                  ├────────────┐       │                 │
     │                  │            │       │                 │
     │                  │◄───────────┘       │                 │
     │                  │                    │                 │
     │                  │ Calculate VolumeProfile              │
     │                  ├────────────┐       │                 │
     │                  │            │       │                 │
     │                  │◄───────────┘       │                 │
     │                  │                    │                 │
     │                  │ Check HTF Levels   │                 │
     │                  ├────────────┐       │                 │
     │                  │            │       │                 │
     │                  │◄───────────┘       │                 │
     │                  │                    │                 │
     │                  │ Score >= 4?        │                 │
     │                  ├────────────┐       │                 │
     │                  │            │       │                 │
     │  signal_dict     │◄───────────┘       │                 │
     │◄─────────────────┤                    │                 │
     │                  │                    │                 │
     │ can_trade()?     │                    │                 │
     ├─────────────────────────────────────► │                 │
     │                  │                    │                 │
     │                  │           Check hours/windows        │
     │                  │                    ├────────┐        │
     │                  │                    │        │        │
     │         True     │                    │◄───────┘        │
     │◄─────────────────────────────────────┤                 │
     │                  │                    │                 │
     │ open_position()  │                    │                 │
     ├────────────────────────────────────────────────────────►│
     │                  │                    │                 │
     │                  │                    │      Execute    │
     │                  │                    │      order      │
     │                  │                    │         ┌───────┤
     │                  │                    │         │       │
     │       ticket     │                    │         └──────►│
     │◄────────────────────────────────────────────────────────┤
     │                  │                    │                 │
```

**Entry Criteria**:
1. ✅ Confluence score >= 4
2. ✅ Within trading hours (Mean Reversion: [5,6,7,9,10,11,12,13] OR Breakout: [3,14,15,16,18,19,20,21,22,23])
3. ✅ Within instrument trading window
4. ✅ Not a holiday/weekend
5. ✅ Max positions limit not exceeded
6. ✅ Risk limits not exceeded (drawdown < 10%, exposure < 15 lots)

---

### 5.2 Recovery Logic

**Grid Example** (EURUSD Buy @ 1.1000):
```
Price     Action              Volume    Stack Total
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1.1000    Original BUY        0.04      0.04
1.0992    Grid Level 1 BUY    0.04      0.08  (-8 pips)
1.0984    Grid Level 2 BUY    0.04      0.12  (-16 pips)
1.0976    Grid Level 3 BUY    0.04      0.16  (-24 pips)

Average Entry: 1.0988
Breakeven: 1.0988 + spread
```

**Hedge Example** (EURUSD Buy @ 1.1000, 8 pips down):
```
Price     Action              Volume    Net Exposure
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1.1000    Original BUY        0.04      +0.04
1.0992    Hedge SELL          0.20      -0.16  (5x)

If price continues down:
  • Original BUY loses
  • Hedge SELL profits 5x faster

If price reverses up:
  • Original BUY recovers
  • Hedge SELL loses (controlled)
```

**DCA Example** (EURUSD Buy @ 1.1000):
```
Price     Action              Volume    Total Volume
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1.1000    Original BUY        0.04      0.04
1.0980    DCA Level 1 BUY     0.08      0.12  (-20 pips, 2x)
1.0960    DCA Level 2 BUY     0.16      0.28  (-40 pips, 4x)
1.0940    DCA Level 3 BUY     0.32      0.60  (-60 pips, 8x)
1.0920    DCA Level 4 BUY     0.64      1.24  (-80 pips, 16x)

Average Entry: ~1.0935
Needs smaller reversal to breakeven
```

---

## 6. Recovery Mechanisms

### 6.1 Recovery Configuration

| Setting | EURUSD | GBPUSD | Description |
|---------|--------|--------|-------------|
| Grid Spacing | 8 pips | 8 pips | Distance between grid levels |
| Grid Volume | 0.04 | 0.04 | Same as original |
| Max Grid Levels | 5 | 5 | Maximum grid entries |
| Hedge Trigger | 8 pips | 8 pips | Pips down before hedge |
| Hedge Ratio | 5.0x | 5.0x | Hedge volume multiplier |
| Max Hedges | 1 | 1 | One hedge per position |
| DCA Trigger | 20 pips | 20 pips | Pips down before DCA |
| DCA Multiplier | 2.0x | 2.0x | Volume doubles each level |
| Max DCA Levels | 4 | 4 | Maximum DCA entries |

### 6.2 Recovery Trigger Conditions

**All recovery mechanisms ONLY trigger when underwater**:

```python
# Buy Position
if position_type == 'buy':
    pips_underwater = (entry_price - current_price) / pip_value
else:  # Sell Position
    pips_underwater = (current_price - entry_price) / pip_value

# Only triggers if pips_underwater > 0 (losing)
```

**Verification**:
- Profitable position (price moved favorably): `pips_underwater = -50` → No recovery ✓
- Losing position (price moved against): `pips_underwater = +50` → Recovery triggers ✓

---

## 7. Exit Logic

### 7.1 Exit Priority Order

Recovery stacks close in this priority:

```
┌─────────────────────────────────────────────────────────────┐
│ 0. STACK DRAWDOWN (Highest Priority - Risk Protection)     │
│    • Net loss > 4x expected profit                         │
│    • Example: $5 expected → kills at -$20 loss             │
│    • Closes ENTIRE stack (original + grid + hedge + DCA)   │
│    • Method: check_stack_drawdown()                        │
└─────────────────────────────────────────────────────────────┘
                            ↓ If not triggered
┌─────────────────────────────────────────────────────────────┐
│ 1. PROFIT TARGET                                            │
│    • Net profit >= 0.5% of account balance                  │
│    • Example: $10,000 account → $50 profit target          │
│    • Closes ENTIRE stack                                    │
│    • Method: check_profit_target()                         │
└─────────────────────────────────────────────────────────────┘
                            ↓ If not triggered
┌─────────────────────────────────────────────────────────────┐
│ 2. TIME LIMIT                                               │
│    • Position open >= 12 hours                              │
│    • Cuts stuck positions                                   │
│    • Closes ENTIRE stack                                    │
│    • Method: check_time_limit()                            │
└─────────────────────────────────────────────────────────────┘
                            ↓ If not triggered
┌─────────────────────────────────────────────────────────────┐
│ 3. VWAP REVERSION                                           │
│    • Buy: Price crosses VWAP from below                     │
│    • Sell: Price crosses VWAP from above                    │
│    • Closes INDIVIDUAL position only (not stack)            │
│    • Method: check_exit_signal()                           │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Exit Code Flow

```python
for ticket in tracked_positions:
    # Get all positions in stack
    stack_tickets = get_all_stack_tickets(ticket)
    all_mt5_positions = mt5.get_positions()

    # 0. Stack Drawdown (NEW)
    if recovery_manager.check_stack_drawdown(ticket, all_mt5_positions, pip_value):
        close_recovery_stack(ticket)  # Kills entire stack
        continue

    # 1. Profit Target
    if recovery_manager.check_profit_target(ticket, all_mt5_positions, balance, 0.5):
        close_recovery_stack(ticket)  # Closes entire stack
        continue

    # 2. Time Limit
    if recovery_manager.check_time_limit(ticket, hours_limit=12):
        close_recovery_stack(ticket)  # Closes entire stack
        continue

    # 3. VWAP Reversion (individual position only)
    if signal_detector.check_exit_signal(position, h1_data):
        mt5.close_position(ticket)  # Closes this position only
        recovery_manager.untrack_position(ticket)
```

### 7.3 Stack Drawdown Calculation

```python
# Example: EURUSD Buy 0.04 lots
symbol = 'EURUSD'
initial_volume = 0.04
tp_pips = 12  # From instruments_config

# Expected profit
expected_profit = 12 * 0.0001 * 0.04 * 100000 = $4.80

# Drawdown threshold
threshold = -1 * ($4.80 * 4.0) = -$19.20

# Stack P&L
original = -$10
grid1    = -$6
grid2    = -$4
hedge    = -$12
──────────────────
net_pl   = -$32

# Check
if -$32 <= -$19.20:
    close_entire_stack()  # YES - Kill it
```

---

## 8. Key Algorithms

### 8.1 VWAP Calculation

```python
def calculate_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """
    Volume-Weighted Average Price with standard deviation bands
    """
    # Typical price
    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3

    # VWAP = sum(typical_price × volume) / sum(volume)
    df['vwap'] = (df['typical_price'] * df['volume']).cumsum() / df['volume'].cumsum()

    # Calculate standard deviation
    df['vwap_deviation'] = (df['typical_price'] - df['vwap']) ** 2
    df['vwap_variance'] = (df['vwap_deviation'] * df['volume']).cumsum() / df['volume'].cumsum()
    df['vwap_std'] = np.sqrt(df['vwap_variance'])

    # Bands
    df['vwap_upper_1sd'] = df['vwap'] + df['vwap_std']
    df['vwap_upper_2sd'] = df['vwap'] + (2 * df['vwap_std'])
    df['vwap_lower_1sd'] = df['vwap'] - df['vwap_std']
    df['vwap_lower_2sd'] = df['vwap'] - (2 * df['vwap_std'])

    return df
```

### 8.2 Volume Profile Calculation

```python
def calculate_volume_profile(df: pd.DataFrame, num_bins: int = 30) -> pd.DataFrame:
    """
    Calculate POC, VAH, VAL from volume distribution
    """
    # Price range
    price_min = df['low'].min()
    price_max = df['high'].max()
    price_bins = np.linspace(price_min, price_max, num_bins + 1)

    # Initialize volume distribution
    volume_dist = np.zeros(num_bins)

    # Distribute volume across price levels
    for _, row in df.iterrows():
        for i in range(num_bins):
            if price_bins[i] <= row['low'] <= price_bins[i+1]:
                # Candle overlaps this bin
                volume_dist[i] += row['volume']

    # POC = Price level with highest volume
    poc_idx = np.argmax(volume_dist)
    df['poc'] = price_bins[poc_idx]

    # Value Area = 70% of volume
    total_volume = volume_dist.sum()
    target_volume = total_volume * 0.70

    # Find VAH/VAL
    sorted_indices = np.argsort(volume_dist)[::-1]  # Descending
    accumulated_volume = 0
    value_area_bins = []

    for idx in sorted_indices:
        accumulated_volume += volume_dist[idx]
        value_area_bins.append(idx)
        if accumulated_volume >= target_volume:
            break

    df['vah'] = price_bins[max(value_area_bins)]  # Value Area High
    df['val'] = price_bins[min(value_area_bins)]  # Value Area Low

    return df
```

### 8.3 Breakout Detection

```python
def detect_breakout(df: pd.DataFrame, lookback: int = 20) -> Dict or None:
    """
    Detect breakouts with volume confirmation
    """
    recent_data = df.tail(lookback)
    latest = df.iloc[-1]

    # Highest high / Lowest low
    highest_high = recent_data['high'].max()
    lowest_low = recent_data['low'].min()

    # Current price
    current_price = latest['close']
    current_volume = latest['volume']
    avg_volume = recent_data['volume'].mean()

    # Volume spike
    volume_spike = current_volume > (avg_volume * 1.5)

    # Bullish breakout
    if current_price > highest_high and volume_spike:
        return {
            'type': 'buy',
            'strength': 2,
            'reason': 'breakout_up'
        }

    # Bearish breakout
    if current_price < lowest_low and volume_spike:
        return {
            'type': 'sell',
            'strength': 2,
            'reason': 'breakout_down'
        }

    return None
```

### 8.4 Position Sizing

```python
def calculate_position_size(symbol: str, account_balance: float) -> float:
    """
    Calculate position size based on risk parameters
    """
    if USE_FIXED_LOT_SIZE:
        return BASE_LOT_SIZE  # 0.04

    # Dynamic sizing (not currently used)
    risk_amount = account_balance * (RISK_PERCENT / 100)  # 1% risk

    # Calculate lot size based on stop loss
    if STOP_LOSS_PIPS:
        pip_value = 10 if 'JPY' in symbol else 1
        risk_per_pip = risk_amount / STOP_LOSS_PIPS
        lot_size = risk_per_pip / pip_value

        # Round to 0.01 step
        lot_size = round(lot_size / 0.01) * 0.01

        # Clamp to limits
        lot_size = max(0.01, min(lot_size, MAX_TOTAL_LOTS))

        return lot_size

    return BASE_LOT_SIZE
```

---

## 9. Configuration Management

### 9.1 Key Configuration Parameters

**File**: `config/strategy_config.py`

```python
# TRADING SYMBOLS
SYMBOLS = ['EURUSD', 'GBPUSD']

# CONFLUENCE SCORING
MIN_CONFLUENCE_SCORE = 4

# POSITION SIZING
BASE_LOT_SIZE = 0.04
USE_FIXED_LOT_SIZE = True
MAX_TOTAL_LOTS = 15.0

# GRID PARAMETERS
GRID_ENABLED = True
GRID_SPACING_PIPS = 8
GRID_LOT_SIZE = 0.04
MAX_GRID_LEVELS = 5

# HEDGE PARAMETERS
HEDGE_ENABLED = True
HEDGE_TRIGGER_PIPS = 8
HEDGE_RATIO = 5.0
MAX_HEDGES_PER_POSITION = 1
STACK_DRAWDOWN_MULTIPLIER = 4.0  # Kill stack at 4x expected loss

# DCA PARAMETERS
DCA_ENABLED = True
DCA_TRIGGER_PIPS = 20
DCA_MAX_LEVELS = 4
DCA_MULTIPLIER = 2.0

# RISK MANAGEMENT
MAX_DRAWDOWN_PERCENT = 10.0  # Account-wide stop
PROFIT_TARGET_PERCENT = 0.5  # Stack profit target
MAX_POSITION_HOURS = 12      # Stack time limit

# TIME FILTERS
MEAN_REVERSION_HOURS = [5, 6, 7, 9, 10, 11, 12, 13]  # GMT
BREAKOUT_HOURS = [3, 14, 15, 16, 18, 19, 20, 21, 22, 23]  # GMT

# PARTIAL CLOSE
PARTIAL_CLOSE_ENABLED = True
PARTIAL_CLOSE_LEVELS = [
    {'percent_to_tp': 50, 'close_percent': 50},
    {'percent_to_tp': 75, 'close_percent': 50},
    {'percent_to_tp': 100, 'close_percent': 100}
]
```

### 9.2 Instrument-Specific Settings

**File**: `portfolio/instruments_config.py`

```python
INSTRUMENTS = {
    'EURUSD': {
        'take_profit_pips': 12,
        'recovery_settings': {
            'grid_spacing_pips': 8,
            'dca_trigger_pips': 20,
            'hedge_trigger_pips': 8,
            'max_grid_levels': 5,
            'max_dca_levels': 4
        },
        'trading_windows': {
            'start_hour': 0,
            'end_hour': 23
        }
    },
    'GBPUSD': {
        'take_profit_pips': 15,
        'recovery_settings': { ... },
        'trading_windows': { ... }
    }
}
```

---

## 10. State Management & Persistence

### 10.1 In-Memory State

The bot maintains state in memory during runtime:

```python
# ConfluenceStrategy
self.market_data_cache = {}      # OHLCV data cache
self.stats = {}                   # Trading statistics

# RecoveryManager
self.tracked_positions = {}       # Position tracking

# PartialCloseManager
self.partial_closes = {}          # Partial close tracking
```

**Note**: State is NOT persisted to disk. On restart, the bot:
- Fetches all open positions from MT5
- Rebuilds tracking state from position comments
- Resumes management

### 10.2 Position Comments

Positions use comments for identification:

```python
# Original positions
comment = f"CONF_{signal['score']}"  # e.g., "CONF_8"

# Recovery orders
comment = f"GRID_{original_ticket}"   # e.g., "GRID_12345"
comment = f"HEDGE_{original_ticket}"  # e.g., "HEDGE_12345"
comment = f"DCA_{original_ticket}"    # e.g., "DCA_12345"
```

This allows the bot to:
- Identify original vs recovery orders
- Link recovery orders to original position
- Rebuild state after restart

---

## 11. Error Handling & Logging

### 11.1 Error Handling Strategy

```python
try:
    # Main trading loop
    for symbol in SYMBOLS:
        try:
            self._manage_positions(symbol)
        except Exception as e:
            print(f"❌ Error managing positions for {symbol}: {e}")
            traceback.print_exc()
            continue  # Skip this symbol, continue with others

        try:
            self._check_for_signals(symbol)
        except Exception as e:
            print(f"❌ Error checking signals for {symbol}: {e}")
            traceback.print_exc()
            continue

except KeyboardInterrupt:
    print("\n🛑 Bot stopped by user")
except Exception as e:
    print(f"❌ Critical error: {e}")
    traceback.print_exc()
finally:
    mt5.shutdown()
```

### 11.2 Logging Levels

```python
# Standard output messages
print("✅ Connected to MT5")           # Success
print("⚠️ Warning: No volume data")    # Warning
print("❌ Error: Position not found")  # Error
print("🔧 Cache cleared")              # Info
print("🛑 Max drawdown reached")       # Critical

# Logger (utils/logger.py)
logger.info("Starting strategy...")
logger.warning("High exposure detected")
logger.error("Failed to close position")
```

---

## 12. Performance Optimization

### 12.1 Data Caching

```python
# Cache market data to avoid repeated MT5 calls
self.market_data_cache = {
    'EURUSD': {
        'h1': pd.DataFrame,  # Refreshed every loop
        'd1': pd.DataFrame,  # Refreshed every loop
        'w1': pd.DataFrame   # Refreshed every loop
    }
}

# Cache lasts for one loop iteration (60 seconds)
```

### 12.2 Loop Timing

```python
# Main loop runs every 60 seconds
while True:
    loop_start = time.time()

    # Execute trading logic
    self._trading_loop()

    # Sleep for remaining time
    loop_duration = time.time() - loop_start
    sleep_time = max(0, 60 - loop_duration)
    time.sleep(sleep_time)
```

### 12.3 MT5 Call Optimization

**Minimized calls**:
- `get_positions()`: Once per loop
- `get_symbol_data()`: Once per symbol per timeframe per loop
- `get_account_info()`: Once per loop

**Batched operations**:
- Process all symbols in one loop
- Check all positions before making decisions

---

## 13. Testing & Validation

### 13.1 Test Mode

```python
# Run with --test-mode flag
python main.py --login X --password Y --server Z --test-mode

# Bypasses:
• Time filters (trades all day)
• Trading windows (always tradeable)

# Still respects:
• Confluence score >= 4
• Risk limits
• Position limits
```

### 13.2 Diagnostic Tools

**diagnose_signals.py**:
```bash
# Analyze last 3 weeks of signals
python diagnose_signals.py

# Shows:
• Total signals detected
• Signals blocked by time filters
• Confluence scores
• Hourly distribution
```

**verify_trading_times.py**:
```bash
# Verify time filters
python verify_trading_times.py

# Shows:
• Current GMT time
• Tradeable symbols
• Active trading windows
```

---

## 14. Deployment

### 14.1 Production Startup

```bash
# Windows (PowerShell)
cd C:\GIT\Ganymede-Prod
python trading_bot\main.py --login 10008829026 --password "XXX" --server MetaQuotes-Demo

# Linux
cd /home/user/Ganymede-Prime
python3 trading_bot/main.py --login 10008829026 --password "XXX" --server MetaQuotes-Demo
```

### 14.2 GUI Mode

```bash
# Launch GUI
python trading_bot/main.py --gui

# GUI allows:
• Start/stop bot
• View positions
• Monitor performance
• See logs in real-time
```

### 14.3 Requirements

```python
# Python 3.8+
pip install MetaTrader5
pip install pandas
pip install numpy
pip install pytz
pip install tk  # For GUI
```

---

## 15. Summary

### 15.1 Trading Strategy Summary

**Type**: Confluence-based Mean Reversion + Breakout
**Win Rate**: 64.3%
**Minimum Score**: 4 (out of possible 13)
**Instruments**: EURUSD, GBPUSD
**Timeframe**: H1 (with D1/W1 confirmation)

**Entry**:
- VWAP band touch (±1σ or ±2σ)
- Volume Profile level (POC/VAH/VAL)
- HTF level (D1/W1 High/Low)
- Breakout with volume confirmation

**Recovery**:
- Grid: Every 8 pips, same size
- Hedge: At 8 pips, 5x opposite direction
- DCA: Every 20 pips, 2x martingale

**Exit**:
- Stack drawdown > 4x expected profit
- Profit target: 0.5% of account
- Time limit: 12 hours
- VWAP reversion

**Risk**:
- Per-stack drawdown limit
- Account-wide 10% drawdown stop
- Maximum 15 lots total exposure

### 15.2 Key Files Reference

| File | Purpose | Lines |
|------|---------|-------|
| `main.py` | Entry point | 150 |
| `confluence_strategy.py` | Main orchestrator | 600 |
| `signal_detector.py` | Signal generation | 250 |
| `recovery_manager.py` | Grid/Hedge/DCA | 850 |
| `partial_close_manager.py` | Profit taking | 200 |
| `mt5_manager.py` | MT5 interface | 500 |
| `strategy_config.py` | Configuration | 400 |

**Total Code**: ~3,000 lines

---

## End of Low-Level Design Document

**Author**: Claude (Anthropic)
**Date**: 2025-12-24
**Version**: 2.0
**Status**: Production

---
