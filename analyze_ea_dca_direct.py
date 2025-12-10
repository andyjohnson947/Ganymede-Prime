#!/usr/bin/env python3
"""
Direct CSV DCA Analysis
Analyzes DCA patterns directly from reverse engineering CSV
"""

import pandas as pd
import numpy as np
from datetime import timedelta


def analyze_ea_dca_patterns(csv_path):
    """Analyze DCA patterns from EA reverse engineering CSV"""
    print("=" * 80)
    print("EA DCA PATTERN ANALYSIS")
    print("Analyzing reverse engineered EA trades for DCA optimization")
    print("=" * 80)

    # Load data
    print(f"\n📥 Loading: {csv_path}")
    df = pd.read_csv(csv_path)
    df['entry_time'] = pd.to_datetime(df['entry_time'])
    df['exit_time'] = pd.to_datetime(df['exit_time'])

    print(f"✅ Loaded {len(df)} trades")
    print(f"   Date range: {df['entry_time'].min()} to {df['entry_time'].max()}")
    print(f"   Total profit: ${df['profit'].sum():.2f}")

    # Detect DCA sequences
    print("\n🔍 Detecting DCA sequences...")

    dca_sequences = []
    df = df.sort_values('entry_time').reset_index(drop=True)

    i = 0
    while i < len(df):
        current = df.iloc[i]
        sequence = [i]

        # Look for consecutive same-direction trades within 48 hours
        j = i + 1
        while j < len(df):
            next_trade = df.iloc[j]

            time_diff_hours = (next_trade['entry_time'] - df.iloc[sequence[0]]['entry_time']).total_seconds() / 3600
            if time_diff_hours > 48:
                break

            # Same direction?
            if next_trade['trade_type'] == current['trade_type']:
                # Adding to losing position?
                if current['trade_type'] == 'buy':
                    is_averaging_down = next_trade['entry_price'] < df.iloc[sequence[-1]]['entry_price']
                else:
                    is_averaging_down = next_trade['entry_price'] > df.iloc[sequence[-1]]['entry_price']

                if is_averaging_down:
                    sequence.append(j)

            j += 1

        # Analyze if 2+ levels
        if len(sequence) >= 2:
            trades = df.iloc[sequence]
            volumes = trades['volume'].values
            prices = trades['entry_price'].values
            profits = trades['profit'].values

            # Calculate metrics
            multipliers = [volumes[k+1] / volumes[k] for k in range(len(volumes)-1)]
            avg_multiplier = np.mean(multipliers)
            total_profit = profits.sum()
            price_decline = abs(prices[-1] - prices[0]) * 10000

            dca_sequences.append({
                'start_idx': sequence[0],
                'end_idx': sequence[-1],
                'levels': len(sequence),
                'direction': trades.iloc[0]['trade_type'],
                'start_price': prices[0],
                'end_price': prices[-1],
                'price_decline_pips': price_decline,
                'start_volume': volumes[0],
                'end_volume': volumes[-1],
                'avg_multiplier': avg_multiplier,
                'total_volume': volumes.sum(),
                'total_profit': total_profit,
                'successful': total_profit > 0,
                'start_time': trades.iloc[0]['entry_time'],
                'end_time': trades.iloc[-1]['exit_time'],
                'duration_hours': (trades.iloc[-1]['exit_time'] - trades.iloc[0]['entry_time']).total_seconds() / 3600,
            })

        i = sequence[-1] + 1 if len(sequence) > 1 else i + 1

    if not dca_sequences:
        print("\n⚠️  No DCA sequences detected")
        return

    print(f"✅ Found {len(dca_sequences)} DCA sequences\n")

    # Analysis by depth
    print("=" * 80)
    print("📊 SUCCESS RATE BY DCA DEPTH")
    print("=" * 80)

    depth_stats = {}
    for depth in range(2, 41):
        depth_seqs = [s for s in dca_sequences if s['levels'] == depth]
        if depth_seqs:
            successful = len([s for s in depth_seqs if s['successful']])
            success_rate = (successful / len(depth_seqs)) * 100
            avg_profit = np.mean([s['total_profit'] for s in depth_seqs])
            avg_multiplier = np.mean([s['avg_multiplier'] for s in depth_seqs])
            avg_decline = np.mean([s['price_decline_pips'] for s in depth_seqs])

            depth_stats[depth] = {
                'count': len(depth_seqs),
                'successful': successful,
                'success_rate': success_rate,
                'avg_profit': avg_profit,
                'avg_multiplier': avg_multiplier,
                'avg_decline': avg_decline,
            }

            if len(depth_seqs) >= 2:  # Only show if multiple samples
                status = "✅" if success_rate >= 60 else "⚠️" if success_rate >= 40 else "❌"
                print(f"{status} {depth:2d} levels: {success_rate:5.1f}% win ({successful}/{len(depth_seqs):2d}) | "
                      f"Avg P/L: ${avg_profit:7.2f} | Mult: {avg_multiplier:.2f}x | "
                      f"Decline: {avg_decline:.1f} pips")

    # Overall statistics
    print("\n" + "=" * 80)
    print("📈 OVERALL STATISTICS")
    print("=" * 80)

    successful = len([s for s in dca_sequences if s['successful']])
    success_rate = (successful / len(dca_sequences)) * 100

    print(f"\nTotal DCA sequences: {len(dca_sequences)}")
    print(f"Successful: {successful} ({success_rate:.1f}%)")
    print(f"Failed: {len(dca_sequences) - successful} ({100-success_rate:.1f}%)")
    print(f"\nAverage levels: {np.mean([s['levels'] for s in dca_sequences]):.1f}")
    print(f"Max levels seen: {max([s['levels'] for s in dca_sequences])}")
    print(f"Min levels seen: {min([s['levels'] for s in dca_sequences])}")
    print(f"\nAverage multiplier: {np.mean([s['avg_multiplier'] for s in dca_sequences]):.2f}x")
    print(f"Average profit: ${np.mean([s['total_profit'] for s in dca_sequences]):.2f}")
    print(f"Average decline: {np.mean([s['price_decline_pips'] for s in dca_sequences]):.1f} pips")
    print(f"Average duration: {np.mean([s['duration_hours'] for s in dca_sequences]):.1f} hours")

    # Best and worst
    print("\n" + "=" * 80)
    print("🏆 TOP 5 BEST SEQUENCES")
    print("=" * 80)

    best = sorted(dca_sequences, key=lambda x: x['total_profit'], reverse=True)[:5]
    for idx, seq in enumerate(best, 1):
        print(f"{idx}. {seq['levels']:2d} levels | ${seq['total_profit']:7.2f} | "
              f"{seq['avg_multiplier']:.2f}x mult | {seq['price_decline_pips']:.1f} pips decline | "
              f"{seq['direction']}")

    print("\n" + "=" * 80)
    print("⚠️  TOP 5 WORST SEQUENCES")
    print("=" * 80)

    worst = sorted(dca_sequences, key=lambda x: x['total_profit'])[:5]
    for idx, seq in enumerate(worst, 1):
        print(f"{idx}. {seq['levels']:2d} levels | ${seq['total_profit']:7.2f} | "
              f"{seq['avg_multiplier']:.2f}x mult | {seq['price_decline_pips']:.1f} pips decline | "
              f"{seq['direction']}")

    # Recommendations
    print("\n" + "=" * 80)
    print("💡 RECOMMENDATIONS")
    print("=" * 80)

    # Find optimal depth
    best_depth = None
    best_rate = 0

    for depth, stats in depth_stats.items():
        if stats['count'] >= 2 and stats['success_rate'] > best_rate:
            best_rate = stats['success_rate']
            best_depth = depth

    if best_depth and depth_stats[best_depth]['count'] >= 2:
        stats = depth_stats[best_depth]
        print(f"\n✅ Optimal DCA Depth: {best_depth} levels")
        print(f"   • Success rate: {stats['success_rate']:.1f}%")
        print(f"   • Average profit: ${stats['avg_profit']:.2f}")
        print(f"   • Sample size: {stats['count']} sequences")
        print(f"\n✅ Recommended Multiplier: {stats['avg_multiplier']:.2f}x")
    else:
        print("\n⚠️  Insufficient data for specific recommendations")

    # Risk warnings
    print("\n🚨 RISK ASSESSMENT:")
    max_levels = max([s['levels'] for s in dca_sequences])
    avg_levels = np.mean([s['levels'] for s in dca_sequences])

    if max_levels > 20:
        print(f"   ❌ CRITICAL: Max {max_levels} levels detected - EXTREMELY HIGH RISK!")
        print(f"      Sequences this deep can blow your account in trending markets")
    elif max_levels > 10:
        print(f"   ⚠️  WARNING: Max {max_levels} levels - HIGH RISK!")
        print(f"      Consider limiting to 5-7 levels maximum")

    if avg_levels > 10:
        print(f"   ⚠️  Average {avg_levels:.1f} levels is too deep")
        print(f"      Recommended: Keep average below 5 levels")

    if success_rate < 50:
        print(f"   ❌ Overall success rate {success_rate:.1f}% is below 50%")
        print(f"      DCA strategy is net losing - needs optimization or disabling")
    elif success_rate < 70:
        print(f"   ⚠️  Success rate {success_rate:.1f}% is marginal")
        print(f"      Aim for 70%+ success rate")
    else:
        print(f"   ✅ Success rate {success_rate:.1f}% is acceptable")

    print("\n" + "=" * 80)
    print("✅ ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python analyze_ea_dca_direct.py ea_reverse_engineering_detailed.csv")
        sys.exit(1)

    try:
        analyze_ea_dca_patterns(sys.argv[1])
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
