#!/usr/bin/env python3
"""
Breakout Trading Timing Analysis
Identifies optimal hours for breakout strategy based on trending conditions
"""

import pandas as pd
import numpy as np
import json

def analyze_breakout_timing(csv_path='ea_reverse_engineering_detailed.csv'):
    """Analyze best times for breakout trading (opposite of mean reversion)"""

    print("="*80)
    print("BREAKOUT TRADING TIMING ANALYSIS")
    print("="*80)

    # Load data
    df = pd.read_csv(csv_path)

    # Convert entry_time to datetime
    df['entry_time'] = pd.to_datetime(df['entry_time'])
    df['exit_time'] = pd.to_datetime(df['exit_time'])

    # Extract time components
    df['hour'] = df['entry_time'].dt.hour
    df['day_of_week'] = df['entry_time'].dt.dayofweek
    df['day_name'] = df['entry_time'].dt.day_name()

    # Define trading sessions
    def get_session(hour):
        if 0 <= hour < 9:
            return 'Tokyo'
        elif 8 <= hour < 17:
            return 'London'
        elif 13 <= hour < 22:
            return 'New York'
        else:
            return 'Sydney'

    df['session'] = df['hour'].apply(get_session)
    df['is_winner'] = df['profit'] > 0
    df['duration_hours'] = (df['exit_time'] - df['entry_time']).dt.total_seconds() / 3600

    # BREAKOUT CONDITIONS (opposite of mean reversion):
    # 1. NOT at VWAP bands (trending, not mean reverting)
    # 2. High volume area (HVN) breakouts
    # 3. Strong momentum (high RSI for buys, low for sells)
    # 4. Higher ATR (volatile periods)
    # 5. NOT at POC/VAH/VAL (breaking through, not bouncing)

    # Identify breakout-style trades
    breakout_trades = df[
        (
            # Not classic mean reversion setups
            (df['in_vwap_band_1'] == False) &
            (df['in_vwap_band_2'] == False) &

            # High volume areas (breaking through resistance)
            ((df['high_volume_area'] == True) | (df['at_lvn'] == True)) &

            # Strong momentum
            (
                ((df['trade_type'] == 'buy') & (df['rsi_14'] > 60)) |
                ((df['trade_type'] == 'sell') & (df['rsi_14'] < 40))
            ) &

            # Higher volatility
            (df['atr_14'] > df['atr_14'].median())
        )
    ].copy()

    print(f"\n📊 Total Trades: {len(df)}")
    print(f"📊 Breakout-Style Trades: {len(breakout_trades)} ({len(breakout_trades)/len(df)*100:.1f}%)")
    print(f"📊 Mean Reversion Trades: {len(df) - len(breakout_trades)} ({(len(df)-len(breakout_trades))/len(df)*100:.1f}%)")

    if len(breakout_trades) < 10:
        print("\n⚠️  Warning: Limited breakout data. Analysis based on trending market conditions.")
        # Fallback: analyze high volatility periods
        breakout_trades = df[
            (df['atr_14'] > df['atr_14'].quantile(0.7)) &  # Top 30% volatility
            (
                ((df['trade_type'] == 'buy') & (df['rsi_14'] > 55)) |
                ((df['trade_type'] == 'sell') & (df['rsi_14'] < 45))
            )
        ].copy()
        print(f"📊 High Volatility Trades (proxy): {len(breakout_trades)}")

    # =========================================================================
    # 1. HOURLY ANALYSIS FOR BREAKOUTS
    # =========================================================================
    print("\n" + "="*80)
    print("1. BEST HOURS FOR BREAKOUT TRADING")
    print("="*80)

    hourly_stats = breakout_trades.groupby('hour').agg({
        'profit': ['count', 'sum', 'mean'],
        'is_winner': 'mean',
        'duration_hours': 'mean',
        'atr_14': 'mean'
    }).round(2)

    hourly_stats.columns = ['trades', 'total_profit', 'avg_profit', 'win_rate', 'avg_duration', 'avg_atr']
    hourly_stats = hourly_stats[hourly_stats['trades'] >= 2]  # At least 2 trades
    hourly_stats['win_rate'] = (hourly_stats['win_rate'] * 100).round(1)
    hourly_stats = hourly_stats.sort_values('avg_atr', ascending=False)  # High volatility = good for breakouts

    print("\n🏆 TOP HOURS (by Volatility & Win Rate):")
    print(hourly_stats.head(10).to_string())

    # =========================================================================
    # 2. SESSION ANALYSIS FOR BREAKOUTS
    # =========================================================================
    print("\n" + "="*80)
    print("2. SESSION PERFORMANCE (BREAKOUT CONDITIONS)")
    print("="*80)

    session_stats = breakout_trades.groupby('session').agg({
        'profit': ['count', 'sum', 'mean'],
        'is_winner': 'mean',
        'duration_hours': 'mean',
        'atr_14': 'mean'
    }).round(2)

    session_stats.columns = ['trades', 'total_profit', 'avg_profit', 'win_rate', 'avg_duration', 'avg_atr']
    session_stats['win_rate'] = (session_stats['win_rate'] * 100).round(1)
    session_stats = session_stats.sort_values('avg_atr', ascending=False)

    print(session_stats.to_string())

    # =========================================================================
    # 3. DAY OF WEEK ANALYSIS
    # =========================================================================
    print("\n" + "="*80)
    print("3. DAY OF WEEK PERFORMANCE (BREAKOUT)")
    print("="*80)

    day_stats = breakout_trades.groupby('day_name').agg({
        'profit': ['count', 'sum', 'mean'],
        'is_winner': 'mean',
        'duration_hours': 'mean',
        'atr_14': 'mean'
    }).round(2)

    day_stats.columns = ['trades', 'total_profit', 'avg_profit', 'win_rate', 'avg_duration', 'avg_atr']
    day_stats['win_rate'] = (day_stats['win_rate'] * 100).round(1)

    # Order by day of week
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_stats = day_stats.reindex([d for d in day_order if d in day_stats.index])

    print(day_stats.to_string())

    # =========================================================================
    # 4. VOLATILITY ANALYSIS
    # =========================================================================
    print("\n" + "="*80)
    print("4. VOLATILITY CHARACTERISTICS")
    print("="*80)

    print(f"\n📈 Average ATR (Breakout trades): {breakout_trades['atr_14'].mean():.5f}")
    print(f"📈 Average ATR (All trades): {df['atr_14'].mean():.5f}")
    print(f"📈 Volatility increase: {(breakout_trades['atr_14'].mean()/df['atr_14'].mean() - 1)*100:.1f}%")

    # =========================================================================
    # 5. RECOMMENDATIONS
    # =========================================================================
    print("\n" + "="*80)
    print("5. BREAKOUT STRATEGY RECOMMENDATIONS")
    print("="*80)

    # Best hours for breakouts (high volatility)
    best_breakout_hours = hourly_stats.nlargest(5, 'avg_atr').index.tolist()
    print(f"\n✅ BREAKOUT HOURS (High Volatility): {best_breakout_hours}")

    # Best sessions
    best_breakout_sessions = session_stats.head(2).index.tolist()
    print(f"✅ BREAKOUT SESSIONS: {best_breakout_sessions}")

    # Best days
    if len(day_stats) > 0:
        best_breakout_days = day_stats.nlargest(3, 'avg_atr').index.tolist()
        print(f"✅ BREAKOUT DAYS: {best_breakout_days}")
    else:
        best_breakout_days = ['Monday', 'Friday']
        print(f"✅ BREAKOUT DAYS (default): {best_breakout_days}")

    print(f"""
📌 BREAKOUT TRADING WINDOWS:

1. BEST HOURS FOR BREAKOUTS:
   {', '.join([f'{h:02d}:00' for h in best_breakout_hours])} UTC

2. BEST SESSIONS:
   {', '.join(best_breakout_sessions)}

3. BEST DAYS:
   {', '.join(best_breakout_days)}

4. ENTRY CONDITIONS:
   - Price breaking weekly high/low
   - Volume > 1.5x average
   - ATR > median (high volatility)
   - RSI >60 (buy) or <40 (sell)
   - NOT at VWAP bands (trending, not reverting)

5. AVOID BREAKOUT TRADING:
   - During mean reversion hours (05:00, 07:00, 09:00)
   - Low volatility periods (ATR < median)
   - At POC/VAH/VAL (these are mean reversion zones)

📌 STRATEGY SEPARATION:

MEAN REVERSION:
   Hours: 05:00, 06:00, 07:00, 09:00, 12:00
   Days: Mon-Fri
   Sessions: Tokyo, London (early)
   Conditions: VWAP bands, POC, Value Area

BREAKOUT:
   Hours: {', '.join([f'{h:02d}:00' for h in best_breakout_hours])}
   Days: {', '.join(best_breakout_days)}
   Sessions: {', '.join(best_breakout_sessions)}
   Conditions: Range breaks, LVN levels, High volume
    """)

    # =========================================================================
    # 6. EXPORT RESULTS
    # =========================================================================
    results = {
        'total_trades': len(df),
        'breakout_trades': len(breakout_trades),
        'best_breakout_hours': [int(h) for h in best_breakout_hours],
        'best_breakout_sessions': best_breakout_sessions,
        'best_breakout_days': best_breakout_days,
        'hourly_stats': hourly_stats.to_dict(),
        'session_stats': session_stats.to_dict(),
        'day_stats': day_stats.to_dict() if len(day_stats) > 0 else {},
        'avg_atr_breakout': float(breakout_trades['atr_14'].mean()),
        'avg_atr_all': float(df['atr_14'].mean())
    }

    with open('breakout_timing_analysis.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n💾 Results saved to: breakout_timing_analysis.json")

    # Save detailed hourly breakdown to CSV
    hourly_stats.to_csv('breakout_hourly_analysis.csv')
    print(f"💾 Hourly analysis saved to: breakout_hourly_analysis.csv")

    return results


if __name__ == '__main__':
    analyze_breakout_timing()
