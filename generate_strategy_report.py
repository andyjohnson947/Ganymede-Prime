#!/usr/bin/env python3
"""
EA Strategy Report Generator
Creates a concise TLDR report of what the EA does and how to implement it
"""

import sys
from pathlib import Path
import pandas as pd
import json
from datetime import datetime
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))


def load_analysis_data():
    """Load all analysis data files"""
    data = {
        'trades': None,
        'confluence': None,
        'htf': None,
        'recovery': None
    }

    # Load trade analysis
    if Path('ea_reverse_engineering_detailed.csv').exists():
        data['trades'] = pd.read_csv('ea_reverse_engineering_detailed.csv')

    # Load confluence analysis
    if Path('confluence_zones_detailed.csv').exists():
        data['confluence'] = pd.read_csv('confluence_zones_detailed.csv')

    # Load HTF multi-timeframe analysis
    if Path('multi_timeframe_analysis.json').exists():
        with open('multi_timeframe_analysis.json', 'r') as f:
            data['htf'] = json.load(f)

    # Load recovery strategy analysis
    if Path('recovery_strategy_analysis.json').exists():
        with open('recovery_strategy_analysis.json', 'r') as f:
            data['recovery'] = json.load(f)

    return data


def analyze_core_strategy(trades_df):
    """Determine core entry strategy"""
    if trades_df is None or trades_df.empty:
        return None

    strategy = {
        'total_trades': len(trades_df),
        'win_rate': 0,
        'avg_profit': 0,
        'primary_signals': [],
        'timeframe': 'H1',  # Default
        'symbols': []
    }

    # Calculate performance
    closed_trades = trades_df[trades_df['exit_time'].notna()]
    if len(closed_trades) > 0:
        strategy['win_rate'] = (closed_trades['profit'] > 0).sum() / len(closed_trades) * 100
        strategy['avg_profit'] = closed_trades['profit'].mean()

    # Identify primary entry signals
    signal_columns = {
        'in_vwap_band_1': 'VWAP Band 1 (±1σ)',
        'in_vwap_band_2': 'VWAP Band 2 (±2σ)',
        'at_swing_high': 'Swing High',
        'at_swing_low': 'Swing Low',
        'at_poc': 'POC (Point of Control)',
        'above_vah': 'Above Value Area High',
        'below_val': 'Below Value Area Low',
        'at_lvn': 'Low Volume Node',
    }

    for col, description in signal_columns.items():
        if col in trades_df.columns:
            usage = trades_df[col].sum()
            if usage > len(trades_df) * 0.1:  # Used in >10% of trades
                strategy['primary_signals'].append({
                    'signal': description,
                    'usage_pct': (usage / len(trades_df)) * 100,
                    'count': int(usage)
                })

    # Get symbols
    if 'symbol' in trades_df.columns:
        strategy['symbols'] = trades_df['symbol'].unique().tolist()

    return strategy


def analyze_confluence_requirements(confluence_df):
    """Determine optimal confluence requirements"""
    if confluence_df is None or confluence_df.empty:
        return None

    confluence = {
        'min_score': 0,
        'optimal_score': 0,
        'high_value_zones': 0,
        'most_common_factors': []
    }

    # Determine optimal score
    if 'confluence_score' in confluence_df.columns:
        # Find score with best win rate
        scores_with_profit = confluence_df[confluence_df['profit'].notna()]
        if not scores_with_profit.empty:
            score_performance = {}
            for score in scores_with_profit['confluence_score'].unique():
                score_trades = scores_with_profit[scores_with_profit['confluence_score'] == score]
                if len(score_trades) >= 5:  # Minimum sample size
                    win_rate = (score_trades['profit'] > 0).sum() / len(score_trades) * 100
                    score_performance[score] = {
                        'win_rate': win_rate,
                        'count': len(score_trades),
                        'avg_profit': score_trades['profit'].mean()
                    }

            if score_performance:
                # Find optimal score (best win rate with reasonable sample)
                optimal = max(score_performance.items(), key=lambda x: x[1]['win_rate'])
                confluence['optimal_score'] = int(optimal[0])
                confluence['optimal_win_rate'] = optimal[1]['win_rate']

        # Count high-value zones
        confluence['high_value_zones'] = len(confluence_df[confluence_df['confluence_score'] >= 3])

    # Most common factors
    if 'factors' in confluence_df.columns:
        all_factors = []
        for factors_str in confluence_df['factors'].dropna():
            if isinstance(factors_str, str):
                all_factors.extend(eval(factors_str))

        if all_factors:
            factor_counts = pd.Series(all_factors).value_counts()
            confluence['most_common_factors'] = [
                {'factor': factor, 'count': int(count)}
                for factor, count in factor_counts.head(5).items()
            ]

    return confluence


def analyze_htf_levels(htf_data):
    """Extract key HTF institutional markers"""
    if not htf_data:
        return None

    htf_summary = {
        'daily_poc': None,
        'weekly_poc': None,
        'prev_week_high': None,
        'prev_week_low': None,
        'prev_week_vwap': None,
        'key_hvn_levels': [],
        'key_lvn_levels': []
    }

    # Daily levels
    daily = htf_data.get('lvn_multi_timeframe', {}).get('D1', {})
    if daily:
        htf_summary['daily_poc'] = daily.get('poc')
        htf_summary['key_hvn_levels'].extend(daily.get('hvn_levels', [])[:3])
        htf_summary['key_lvn_levels'].extend(daily.get('lvn_levels', [])[:3])

    # Weekly levels
    weekly = htf_data.get('lvn_multi_timeframe', {}).get('W1', {})
    if weekly:
        htf_summary['weekly_poc'] = weekly.get('poc')

    # Previous week
    prev_week = htf_data.get('previous_week_levels', {})
    if prev_week:
        htf_summary['prev_week_high'] = prev_week.get('high')
        htf_summary['prev_week_low'] = prev_week.get('low')
        vwap_bands = prev_week.get('vwap_bands', {})
        if vwap_bands:
            htf_summary['prev_week_vwap'] = vwap_bands.get('vwap')

    return htf_summary


def analyze_recovery_mechanics(recovery_data):
    """Summarize recovery mechanisms"""
    if not recovery_data:
        return None

    recovery = {
        'uses_grid': False,
        'uses_hedge': False,
        'uses_dca': False,
        'grid_spacing': None,
        'hedge_ratio': None,
        'dca_optimal_depth': None,
        'martingale_multiplier': None,
        'max_exposure': None
    }

    # Check what's being used
    if recovery_data.get('grid_sequences', 0) > 0:
        recovery['uses_grid'] = True

    if recovery_data.get('hedge_pairs', 0) > 0:
        recovery['uses_hedge'] = True

    if recovery_data.get('dca_sequences', 0) > 0:
        recovery['uses_dca'] = True

    # Risk metrics
    risk = recovery_data.get('risk_metrics', {})
    if risk:
        recovery['max_exposure'] = risk.get('max_exposure')

    return recovery


def generate_implementation_code(strategy, confluence, htf, recovery):
    """Generate Python implementation guidelines"""

    code_sections = []

    # 1. Entry Signal Detection
    code_sections.append("""
# =============================================================================
# ENTRY SIGNAL DETECTION
# =============================================================================

def detect_entry_signal(current_data, htf_levels):
    \"\"\"
    Detect entry signals based on EA reverse engineering

    Args:
        current_data: Current market data (OHLCV + indicators)
        htf_levels: Higher timeframe institutional levels

    Returns:
        dict with signal info or None
    \"\"\"
    signal = {
        'should_trade': False,
        'direction': None,
        'confluence_score': 0,
        'factors': []
    }

    current_price = current_data['close']
    confluence_score = 0
    factors = []
""")

    # Add VWAP checking
    if strategy and strategy.get('primary_signals'):
        vwap_signals = [s for s in strategy['primary_signals'] if 'VWAP' in s['signal']]
        if vwap_signals:
            code_sections.append("""
    # Check VWAP bands (PRIMARY SIGNAL)
    vwap = current_data.get('VWAP')
    vwap_std = calculate_vwap_std(current_data)  # You need to implement this

    if vwap and vwap_std:
        # Band 1 (±1σ)
        if vwap - vwap_std <= current_price <= vwap + vwap_std:
            confluence_score += 1
            factors.append('VWAP Band 1')
            signal['direction'] = 'buy' if current_price < vwap else 'sell'

        # Band 2 (±2σ)
        elif vwap - (vwap_std * 2) <= current_price <= vwap + (vwap_std * 2):
            confluence_score += 1
            factors.append('VWAP Band 2')
            signal['direction'] = 'buy' if current_price < vwap else 'sell'
""")

    # Add HTF checking
    if htf:
        code_sections.append("""
    # Check HTF institutional levels (CRITICAL)
    tolerance = current_price * 0.003  # 0.3% tolerance

    # Daily HVN levels (strong S/R)
    for hvn in htf_levels.get('daily_hvn', []):
        if abs(current_price - hvn) < tolerance:
            confluence_score += 2
            factors.append('Daily HVN')
            break

    # Weekly POC (institutional magnet)
    weekly_poc = htf_levels.get('weekly_poc')
    if weekly_poc and abs(current_price - weekly_poc) < tolerance:
        confluence_score += 3
        factors.append('Weekly POC')

    # Previous Week High/Low
    prev_high = htf_levels.get('prev_week_high')
    prev_low = htf_levels.get('prev_week_low')

    if prev_high and abs(current_price - prev_high) < tolerance:
        confluence_score += 2
        factors.append('Previous Week High')
    elif prev_low and abs(current_price - prev_low) < tolerance:
        confluence_score += 2
        factors.append('Previous Week Low')
""")

    # Add confluence check
    min_confluence = confluence.get('optimal_score', 4) if confluence else 4
    code_sections.append(f"""
    # Decision: Trade only with sufficient confluence
    signal['confluence_score'] = confluence_score
    signal['factors'] = factors
    signal['should_trade'] = confluence_score >= {min_confluence}

    return signal if signal['should_trade'] else None
""")

    # 2. Position Sizing
    code_sections.append("""

# =============================================================================
# POSITION SIZING
# =============================================================================

def calculate_position_size(account_balance, risk_percent=1.0):
    \"\"\"
    Calculate position size based on account balance

    Args:
        account_balance: Current account balance
        risk_percent: Risk per trade as percentage (default 1%)

    Returns:
        float: Lot size
    \"\"\"
    risk_amount = account_balance * (risk_percent / 100)
    # Adjust based on your broker's lot size requirements
    lot_size = round(risk_amount / 10000, 2)  # Example calculation

    # Ensure within limits
    lot_size = max(0.01, min(lot_size, 1.0))

    return lot_size
""")

    # 3. Recovery Strategy
    if recovery and recovery.get('uses_grid'):
        code_sections.append(f"""

# =============================================================================
# GRID RECOVERY STRATEGY
# =============================================================================

GRID_SPACING_PIPS = {recovery.get('grid_spacing', 10.8)}  # From EA analysis
MAX_GRID_LEVELS = 6  # Maximum grid positions
GRID_LOT_SIZE = 0.02  # Fixed lot per level

def should_add_grid_level(entry_price, current_price, existing_levels):
    \"\"\"Check if we should add another grid level\"\"\"
    if len(existing_levels) >= MAX_GRID_LEVELS:
        return False

    pips_moved = abs(current_price - entry_price) * 10000

    # Add grid level every GRID_SPACING_PIPS
    expected_levels = int(pips_moved / GRID_SPACING_PIPS) + 1

    return expected_levels > len(existing_levels)
""")

    if recovery and recovery.get('uses_hedge'):
        code_sections.append(f"""

# =============================================================================
# HEDGING STRATEGY
# =============================================================================

HEDGE_ENABLED = True
HEDGE_TRIGGER_PIPS = 8  # Trigger hedge after X pips underwater
HEDGE_RATIO = 2.4  # Overhedge ratio

def should_activate_hedge(entry_price, current_price, trade_type, has_hedge):
    \"\"\"Determine if we should place a hedge\"\"\"
    if has_hedge or not HEDGE_ENABLED:
        return False

    # Calculate underwater amount
    if trade_type == 'buy':
        pips_underwater = (entry_price - current_price) * 10000
    else:
        pips_underwater = (current_price - entry_price) * 10000

    return pips_underwater >= HEDGE_TRIGGER_PIPS

def calculate_hedge_size(original_position_size):
    \"\"\"Calculate hedge position size\"\"\"
    return round(original_position_size * HEDGE_RATIO, 2)
""")

    if recovery and recovery.get('uses_dca'):
        code_sections.append(f"""

# =============================================================================
# DCA / MARTINGALE STRATEGY
# =============================================================================

MAX_DCA_LEVELS = {recovery.get('dca_optimal_depth', 3)}  # Optimal depth from analysis
MARTINGALE_MULTIPLIER = 1.4  # Lot size multiplier per level

def should_add_dca_level(entry_price, current_price, trade_type, current_level):
    \"\"\"Determine if we should add DCA level\"\"\"
    if current_level >= MAX_DCA_LEVELS:
        return False

    # Calculate price decline
    if trade_type == 'buy':
        pips_decline = (entry_price - current_price) * 10000
    else:
        pips_decline = (current_price - entry_price) * 10000

    # Add DCA level every ~10 pips decline
    expected_level = int(pips_decline / 10) + 1

    return expected_level > current_level

def calculate_dca_lot_size(base_lot_size, level):
    \"\"\"Calculate lot size for DCA level with martingale\"\"\"
    return round(base_lot_size * (MARTINGALE_MULTIPLIER ** level), 2)
""")

    # 4. Exit Strategy
    code_sections.append("""

# =============================================================================
# EXIT STRATEGY
# =============================================================================

TP_MODE = 'vwap_reversion'  # Exit when price returns to VWAP
TAKE_PROFIT_PIPS = 60.0  # Alternative TP distance

def should_close_position(entry_price, current_price, trade_type, vwap):
    \"\"\"Determine if position should be closed\"\"\"

    if TP_MODE == 'vwap_reversion':
        # Close when price returns to VWAP
        if trade_type == 'buy':
            return current_price >= vwap
        else:
            return current_price <= vwap

    else:
        # Close at fixed pip target
        if trade_type == 'buy':
            pips_profit = (current_price - entry_price) * 10000
        else:
            pips_profit = (entry_price - current_price) * 10000

        return pips_profit >= TAKE_PROFIT_PIPS
""")

    # 5. Main Trading Loop
    code_sections.append("""

# =============================================================================
# MAIN TRADING LOOP
# =============================================================================

def main_trading_loop():
    \"\"\"Main trading logic\"\"\"

    while True:
        # Get current market data
        current_data = get_market_data()  # You implement this
        htf_levels = get_htf_levels()  # Load HTF institutional levels

        # Check for entry signal
        signal = detect_entry_signal(current_data, htf_levels)

        if signal:
            # Calculate position size
            lot_size = calculate_position_size(get_account_balance())

            # Place trade
            trade_id = place_order(
                symbol='EURUSD',
                order_type=signal['direction'],
                lot_size=lot_size,
                confluence_score=signal['confluence_score']
            )

            print(f"📊 Entry: {signal['direction'].upper()} @ {current_data['close']}")
            print(f"   Confluence: {signal['confluence_score']}")
            print(f"   Factors: {', '.join(signal['factors'])}")

        # Monitor existing positions
        for position in get_open_positions():
            # Check exit conditions
            if should_close_position(
                position['entry_price'],
                current_data['close'],
                position['type'],
                current_data['VWAP']
            ):
                close_position(position['id'])
                print(f"✅ Exit: {position['type'].upper()} @ {current_data['close']}")

            # Check recovery mechanisms
            elif should_add_grid_level(
                position['entry_price'],
                current_data['close'],
                position['grid_levels']
            ):
                add_grid_level(position['id'], GRID_LOT_SIZE)
                print(f"📐 Grid: Added level @ {current_data['close']}")

            elif should_activate_hedge(
                position['entry_price'],
                current_data['close'],
                position['type'],
                position['has_hedge']
            ):
                hedge_size = calculate_hedge_size(position['lot_size'])
                opposite_type = 'sell' if position['type'] == 'buy' else 'buy'
                place_hedge(position['id'], opposite_type, hedge_size)
                print(f"⚖️  Hedge: {opposite_type.upper()} @ {current_data['close']}")

        # Sleep until next bar
        time.sleep(3600)  # 1 hour for H1 timeframe


if __name__ == '__main__':
    main_trading_loop()
""")

    return '\n'.join(code_sections)


def generate_report():
    """Generate comprehensive EA strategy report"""

    print("=" * 80)
    print("EA STRATEGY REPORT - COMPREHENSIVE TLDR")
    print("=" * 80)
    print()

    # Load all data
    print("📥 Loading analysis data...")
    data = load_analysis_data()

    # Check if we have at least some data
    has_data = False
    if data['trades'] is not None and not data['trades'].empty:
        has_data = True
    if data['confluence'] is not None and not data['confluence'].empty:
        has_data = True
    if data['htf'] is not None:
        has_data = True
    if data['recovery'] is not None:
        has_data = True

    if not has_data:
        print("\n❌ No analysis data found!")
        print("   Please run the following first:")
        print("   1. Analyze My EA (Option 1)")
        print("   2. Analyze Confluence Zones (Option 2)")
        print("   3. Deep Dive: Recovery Strategies (Option 3)")
        return

    print("✅ Data loaded successfully")
    print()

    # Analyze each component
    strategy = analyze_core_strategy(data['trades'])
    confluence = analyze_confluence_requirements(data['confluence'])
    htf = analyze_htf_levels(data['htf'])
    recovery = analyze_recovery_mechanics(data['recovery'])

    # ========== EXECUTIVE SUMMARY ==========
    print("=" * 80)
    print("📋 EXECUTIVE SUMMARY")
    print("=" * 80)
    print()

    if strategy:
        print(f"Total Trades Analyzed: {strategy['total_trades']}")
        print(f"Overall Win Rate: {strategy['win_rate']:.1f}%")
        print(f"Average Profit per Trade: ${strategy['avg_profit']:.2f}")
        print(f"Symbols: {', '.join(strategy['symbols'])}")
        print(f"Primary Timeframe: {strategy['timeframe']}")
    print()

    # ========== CORE STRATEGY ==========
    print("=" * 80)
    print("🎯 WHAT THE EA DOES - CORE STRATEGY")
    print("=" * 80)
    print()

    print("Entry Methodology:")
    print("-" * 80)
    if strategy and strategy['primary_signals']:
        print("The EA enters trades based on confluence of multiple factors:")
        print()
        for signal in strategy['primary_signals']:
            print(f"  • {signal['signal']}")
            print(f"    Used in {signal['usage_pct']:.1f}% of trades ({signal['count']} times)")
    else:
        print("  Unable to determine entry signals from data")
    print()

    if confluence:
        print(f"Confluence Requirements:")
        print(f"  • Minimum confluence score: {confluence.get('optimal_score', 'Unknown')}")
        if confluence.get('optimal_win_rate'):
            print(f"  • Win rate at optimal score: {confluence['optimal_win_rate']:.1f}%")
        print(f"  • High-value setups (3+ factors): {confluence['high_value_zones']}")
        print()

        if confluence.get('most_common_factors'):
            print("Most Important Confluence Factors:")
            for factor_info in confluence['most_common_factors']:
                print(f"  • {factor_info['factor']} - appears {factor_info['count']} times")
    print()

    # ========== HTF ANALYSIS ==========
    if htf:
        print("=" * 80)
        print("📊 HIGHER TIMEFRAME INSTITUTIONAL LEVELS")
        print("=" * 80)
        print()

        print("The EA respects key institutional levels:")
        if htf.get('daily_poc'):
            print(f"  • Daily POC: {htf['daily_poc']:.5f}")
        if htf.get('weekly_poc'):
            print(f"  • Weekly POC: {htf['weekly_poc']:.5f}")
        if htf.get('prev_week_high'):
            print(f"  • Previous Week High: {htf['prev_week_high']:.5f}")
        if htf.get('prev_week_low'):
            print(f"  • Previous Week Low: {htf['prev_week_low']:.5f}")
        if htf.get('prev_week_vwap'):
            print(f"  • Previous Week VWAP: {htf['prev_week_vwap']:.5f}")
        print()

        if htf.get('key_hvn_levels'):
            print("Key HVN Levels (Strong S/R):")
            for i, hvn in enumerate(htf['key_hvn_levels'][:3], 1):
                print(f"  {i}. {hvn:.5f}")
        print()

    # ========== RECOVERY MECHANISMS ==========
    if recovery:
        print("=" * 80)
        print("🔧 RECOVERY MECHANISMS")
        print("=" * 80)
        print()

        mechanisms = []
        if recovery.get('uses_grid'):
            mechanisms.append("Grid Trading")
        if recovery.get('uses_hedge'):
            mechanisms.append("Hedging")
        if recovery.get('uses_dca'):
            mechanisms.append("DCA/Martingale")

        if mechanisms:
            print(f"The EA uses: {', '.join(mechanisms)}")
            print()

            if recovery.get('uses_grid'):
                print("Grid Trading:")
                if recovery.get('grid_spacing'):
                    print(f"  • Spacing: {recovery['grid_spacing']:.1f} pips")
                print(f"  • Adds positions at regular intervals when underwater")

            if recovery.get('uses_hedge'):
                print("\nHedging:")
                if recovery.get('hedge_ratio'):
                    print(f"  • Ratio: {recovery['hedge_ratio']:.1f}x (overhedge)")
                print(f"  • Triggers when position moves against entry")

            if recovery.get('uses_dca'):
                print("\nDCA/Martingale:")
                if recovery.get('dca_optimal_depth'):
                    print(f"  • Optimal depth: {recovery['dca_optimal_depth']} levels")
                if recovery.get('martingale_multiplier'):
                    print(f"  • Lot multiplier: {recovery['martingale_multiplier']:.1f}x")
                print(f"  • Averages down losing positions")

            print()
            if recovery.get('max_exposure'):
                print(f"Maximum Exposure: {recovery['max_exposure']:.2f} lots")
        print()

    # ========== KEY INSIGHTS ==========
    print("=" * 80)
    print("💡 KEY INSIGHTS")
    print("=" * 80)
    print()

    insights = []

    if strategy and strategy['win_rate'] > 60:
        insights.append(f"✅ Strong win rate ({strategy['win_rate']:.1f}%) indicates solid strategy")
    elif strategy and strategy['win_rate'] < 50:
        insights.append(f"⚠️  Low win rate ({strategy['win_rate']:.1f}%) - relies heavily on recovery")

    if confluence and confluence.get('optimal_score', 0) >= 4:
        insights.append(f"✅ High confluence requirement ({confluence['optimal_score']}) = quality over quantity")
    elif confluence and confluence.get('optimal_score', 0) <= 2:
        insights.append(f"⚠️  Low confluence requirement - may overtrade")

    if recovery:
        if recovery.get('uses_grid') and recovery.get('uses_hedge') and recovery.get('uses_dca'):
            insights.append("⚠️  Uses ALL recovery methods - high risk but aggressive recovery")
        elif recovery.get('uses_hedge'):
            insights.append("✅ Uses hedging - provides protection but locks in drawdown")

    if htf:
        insights.append("✅ Respects HTF levels - institutional approach")

    for insight in insights:
        print(f"  {insight}")
    print()

    # ========== IMPLEMENTATION GUIDE ==========
    print("=" * 80)
    print("🚀 PYTHON IMPLEMENTATION GUIDE")
    print("=" * 80)
    print()

    print("To implement this EA in Python, you need:")
    print()
    print("1. Market Data Pipeline:")
    print("   • Real-time OHLCV data feed (H1 timeframe)")
    print("   • VWAP calculation with standard deviation bands")
    print("   • Volume profile calculation (POC, VAH, VAL)")
    print("   • HTF data (Daily, Weekly levels)")
    print()

    print("2. Signal Detection:")
    if confluence and confluence.get('optimal_score'):
        print(f"   • Check {len(confluence.get('most_common_factors', []))} primary factors")
        print(f"   • Require minimum confluence score of {confluence['optimal_score']}")
    print("   • Validate against HTF institutional levels")
    print()

    print("3. Position Management:")
    print("   • Entry: Confluence-based signals")
    print("   • Exit: VWAP reversion or fixed pip target")
    if recovery:
        if recovery.get('uses_grid'):
            print("   • Grid: Add levels every ~10 pips underwater")
        if recovery.get('uses_hedge'):
            print("   • Hedge: Activate when 8 pips underwater")
        if recovery.get('uses_dca'):
            print(f"   • DCA: Maximum {recovery.get('dca_optimal_depth', 3)} levels")
    print()

    print("4. Risk Management:")
    print("   • Risk 1% per trade")
    if recovery and recovery.get('max_exposure'):
        print(f"   • Maximum total exposure: {recovery['max_exposure']:.2f} lots")
    print("   • Stop trading at 10% drawdown")
    print()

    # ========== EXPORT CODE ==========
    print("=" * 80)
    print("💾 EXPORTING IMPLEMENTATION CODE")
    print("=" * 80)
    print()

    implementation_code = generate_implementation_code(strategy, confluence, htf, recovery)

    # Save to file
    with open('ea_python_implementation.py', 'w', encoding='utf-8') as f:
        f.write('#!/usr/bin/env python3\n')
        f.write('"""\n')
        f.write('EA Python Implementation - Generated from Reverse Engineering\n')
        f.write(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write('"""\n\n')
        f.write('import time\n')
        f.write(implementation_code)

    print("✅ Implementation code saved to: ea_python_implementation.py")
    print()

    # Save report summary
    report_summary = {
        'generation_date': datetime.now().isoformat(),
        'strategy': strategy,
        'confluence': confluence,
        'htf_summary': htf,
        'recovery': recovery,
        'insights': insights
    }

    with open('ea_strategy_report.json', 'w', encoding='utf-8') as f:
        json.dump(report_summary, f, indent=2, default=str)

    print("✅ Report summary saved to: ea_strategy_report.json")
    print()

    print("=" * 80)
    print("✨ NEXT STEPS")
    print("=" * 80)
    print()
    print("1. Review ea_python_implementation.py")
    print("2. Implement the helper functions:")
    print("   • get_market_data()")
    print("   • get_htf_levels()")
    print("   • place_order() / close_position()")
    print("3. Connect to your broker's API (MT5, OANDA, etc.)")
    print("4. Backtest the implementation")
    print("5. Paper trade before going live")
    print()

    print("=" * 80)
    print("REPORT COMPLETE")
    print("=" * 80)


if __name__ == '__main__':
    try:
        generate_report()
    except KeyboardInterrupt:
        print("\n\n⏹️  Cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
