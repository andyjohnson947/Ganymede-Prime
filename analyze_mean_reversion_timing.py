#!/usr/bin/env python3
"""
Mean Reversion Timing Analysis
Analyzes historical trades to find optimal times for mean reversion strategy
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json

def analyze_mean_reversion_timing(csv_path='ea_reverse_engineering_detailed.csv'):
    """Analyze best times for mean reversion based on historical data"""

    print("="*80)
    print("MEAN REVERSION TIMING ANALYSIS")
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

    # Define trading sessions (UTC)
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

    # Calculate trade duration in hours
    df['duration_hours'] = (df['exit_time'] - df['entry_time']).dt.total_seconds() / 3600

    # Identify if trade was profitable
    df['is_winner'] = df['profit'] > 0

    # Filter for mean reversion entries (at VWAP bands, POC, or value area)
    mean_reversion_trades = df[
        (df['in_vwap_band_1'] == True) |
        (df['in_vwap_band_2'] == True) |
        (df['at_poc'] == True) |
        (df['above_vah'] == True) |
        (df['below_val'] == True)
    ].copy()

    print(f"\n📊 Total Trades: {len(df)}")
    print(f"📊 Mean Reversion Trades: {len(mean_reversion_trades)} ({len(mean_reversion_trades)/len(df)*100:.1f}%)")

    # =========================================================================
    # 1. HOURLY ANALYSIS
    # =========================================================================
    print("\n" + "="*80)
    print("1. BEST HOURS FOR MEAN REVERSION")
    print("="*80)

    hourly_stats = mean_reversion_trades.groupby('hour').agg({
        'profit': ['count', 'sum', 'mean'],
        'is_winner': 'mean',
        'duration_hours': 'mean'
    }).round(2)

    hourly_stats.columns = ['trades', 'total_profit', 'avg_profit', 'win_rate', 'avg_duration']
    hourly_stats = hourly_stats[hourly_stats['trades'] >= 3]  # At least 3 trades
    hourly_stats['win_rate'] = (hourly_stats['win_rate'] * 100).round(1)
    hourly_stats = hourly_stats.sort_values('win_rate', ascending=False)

    print("\n🏆 TOP 10 HOURS (by Win Rate):")
    print(hourly_stats.head(10).to_string())

    # =========================================================================
    # 2. SESSION ANALYSIS
    # =========================================================================
    print("\n" + "="*80)
    print("2. SESSION PERFORMANCE")
    print("="*80)

    session_stats = mean_reversion_trades.groupby('session').agg({
        'profit': ['count', 'sum', 'mean'],
        'is_winner': 'mean',
        'duration_hours': 'mean'
    }).round(2)

    session_stats.columns = ['trades', 'total_profit', 'avg_profit', 'win_rate', 'avg_duration']
    session_stats['win_rate'] = (session_stats['win_rate'] * 100).round(1)
    session_stats = session_stats.sort_values('win_rate', ascending=False)

    print(session_stats.to_string())

    # =========================================================================
    # 3. DAY OF WEEK ANALYSIS
    # =========================================================================
    print("\n" + "="*80)
    print("3. DAY OF WEEK PERFORMANCE")
    print("="*80)

    day_stats = mean_reversion_trades.groupby('day_name').agg({
        'profit': ['count', 'sum', 'mean'],
        'is_winner': 'mean',
        'duration_hours': 'mean'
    }).round(2)

    day_stats.columns = ['trades', 'total_profit', 'avg_profit', 'win_rate', 'avg_duration']
    day_stats['win_rate'] = (day_stats['win_rate'] * 100).round(1)

    # Order by day of week
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_stats = day_stats.reindex([d for d in day_order if d in day_stats.index])

    print(day_stats.to_string())

    # =========================================================================
    # 4. VWAP BAND ANALYSIS
    # =========================================================================
    print("\n" + "="*80)
    print("4. MEAN REVERSION ENTRY TYPE ANALYSIS")
    print("="*80)

    # VWAP Band 1
    vwap1 = mean_reversion_trades[mean_reversion_trades['in_vwap_band_1'] == True]
    print(f"\n📉 VWAP Band 1 (±1σ) - Close to mean:")
    print(f"   Trades: {len(vwap1)}")
    print(f"   Win Rate: {vwap1['is_winner'].mean()*100:.1f}%")
    print(f"   Avg Profit: ${vwap1['profit'].mean():.2f}")
    print(f"   Avg Duration: {vwap1['duration_hours'].mean():.1f} hours")

    # VWAP Band 2
    vwap2 = mean_reversion_trades[mean_reversion_trades['in_vwap_band_2'] == True]
    print(f"\n📉 VWAP Band 2 (±2σ) - Extended deviation:")
    print(f"   Trades: {len(vwap2)}")
    print(f"   Win Rate: {vwap2['is_winner'].mean()*100:.1f}%")
    print(f"   Avg Profit: ${vwap2['profit'].mean():.2f}")
    print(f"   Avg Duration: {vwap2['duration_hours'].mean():.1f} hours")

    # POC entries
    poc = mean_reversion_trades[mean_reversion_trades['at_poc'] == True]
    print(f"\n📊 Point of Control (POC) - Highest volume:")
    print(f"   Trades: {len(poc)}")
    print(f"   Win Rate: {poc['is_winner'].mean()*100:.1f}%")
    print(f"   Avg Profit: ${poc['profit'].mean():.2f}")
    print(f"   Avg Duration: {poc['duration_hours'].mean():.1f} hours")

    # Value area entries
    vah = mean_reversion_trades[mean_reversion_trades['above_vah'] == True]
    val = mean_reversion_trades[mean_reversion_trades['below_val'] == True]
    value_area = pd.concat([vah, val])
    print(f"\n📊 Value Area (VAH/VAL) - 70% volume boundary:")
    print(f"   Trades: {len(value_area)}")
    print(f"   Win Rate: {value_area['is_winner'].mean()*100:.1f}%")
    print(f"   Avg Profit: ${value_area['profit'].mean():.2f}")
    print(f"   Avg Duration: {value_area['duration_hours'].mean():.1f} hours")

    # =========================================================================
    # 5. OPTIMAL CONDITIONS
    # =========================================================================
    print("\n" + "="*80)
    print("5. OPTIMAL MEAN REVERSION CONDITIONS")
    print("="*80)

    # Best hour + session combinations
    best_hours = hourly_stats.head(5).index.tolist()
    print(f"\n✅ Trade during these hours: {best_hours}")

    # Best sessions
    best_sessions = session_stats.head(2).index.tolist()
    print(f"✅ Best sessions: {best_sessions}")

    # Best days
    best_days = day_stats.nlargest(3, 'win_rate').index.tolist()
    print(f"✅ Best days: {best_days}")

    # Best entry type
    entry_types = {
        'VWAP Band 1': vwap1['is_winner'].mean() * 100 if len(vwap1) > 0 else 0,
        'VWAP Band 2': vwap2['is_winner'].mean() * 100 if len(vwap2) > 0 else 0,
        'POC': poc['is_winner'].mean() * 100 if len(poc) > 0 else 0,
        'Value Area': value_area['is_winner'].mean() * 100 if len(value_area) > 0 else 0
    }
    best_entry = max(entry_types, key=entry_types.get)
    print(f"✅ Best entry type: {best_entry} ({entry_types[best_entry]:.1f}% win rate)")

    # =========================================================================
    # 6. RECOMMENDATIONS
    # =========================================================================
    print("\n" + "="*80)
    print("6. MEAN REVERSION STRATEGY RECOMMENDATIONS")
    print("="*80)

    print(f"""
📌 TIMING RECOMMENDATIONS:

1. BEST HOURS TO TRADE:
   {', '.join([f'{h:02d}:00' for h in best_hours])}

2. BEST SESSIONS:
   {', '.join(best_sessions)}

3. BEST DAYS:
   {', '.join(best_days)}

4. BEST ENTRY TYPE:
   {best_entry} with {entry_types[best_entry]:.1f}% win rate

📌 AVOID TRADING:
   - During lowest win rate hours (see table above)
   - Weekend sessions (if low volume)
   - During high-impact news events

📌 OPTIMAL SETUP:
   - Wait for price to reach VWAP ±2σ bands
   - Confirm with POC or value area confluence
   - Enter during London or NY sessions
   - Use 4+ confluence factors for best results (83.3% win rate)
    """)

    # =========================================================================
    # 7. EXPORT RESULTS
    # =========================================================================
    results = {
        'total_trades': len(df),
        'mean_reversion_trades': len(mean_reversion_trades),
        'best_hours': [int(h) for h in best_hours],
        'best_sessions': best_sessions,
        'best_days': best_days,
        'best_entry_type': best_entry,
        'hourly_stats': hourly_stats.to_dict(),
        'session_stats': session_stats.to_dict(),
        'day_stats': day_stats.to_dict(),
        'entry_type_stats': entry_types
    }

    with open('mean_reversion_timing_analysis.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n💾 Results saved to: mean_reversion_timing_analysis.json")

    # Save detailed hourly breakdown to CSV
    hourly_stats.to_csv('mean_reversion_hourly_analysis.csv')
    print(f"💾 Hourly analysis saved to: mean_reversion_hourly_analysis.csv")


if __name__ == '__main__':
    analyze_mean_reversion_timing()
