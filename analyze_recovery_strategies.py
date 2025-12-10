#!/usr/bin/env python3
"""
Deep Dive Recovery Strategy Analysis
Comprehensive investigation of hedging, DCA, martingale, timing, and leverage
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))


def load_trades_from_db(db_path='data/trading_data.db'):
    """Load all trades from database"""
    print(f"\n📥 Loading trades from database...")

    try:
        if not Path(db_path).exists():
            print(f"❌ Database not found: {db_path}")
            return pd.DataFrame()

        conn = sqlite3.connect(db_path)

        # Load deals and reconstruct trades
        query = """
        SELECT
            ticket, [order], position_id, time, type, entry,
            symbol, volume, price, profit, commission, swap,
            magic, comment
        FROM historical_deals
        ORDER BY position_id, time
        """

        deals_df = pd.read_sql_query(query, conn)
        conn.close()

        if deals_df.empty:
            print("❌ No deals found in database")
            return pd.DataFrame()

        deals_df['time'] = pd.to_datetime(deals_df['time'])
        trades = []

        for position_id in deals_df['position_id'].unique():
            if pd.isna(position_id):
                continue

            position_deals = deals_df[deals_df['position_id'] == position_id].sort_values('time')

            # Get entry deal
            entry_deals = position_deals[position_deals['entry'].isin([0, 2])]
            if entry_deals.empty:
                continue

            entry_deal = entry_deals.iloc[0]

            # Get exit deal
            exit_deals = position_deals[position_deals['entry'].isin([1, 2, 3])]
            exit_deal = exit_deals.iloc[-1] if not exit_deals.empty else None

            trade_type = 'buy' if entry_deal['type'] == 0 else 'sell'

            # Calculate totals
            position_profit = position_deals['profit'].sum()
            position_commission = position_deals['commission'].sum()
            position_swap = position_deals['swap'].sum()

            trade = {
                'ticket': int(position_id),
                'position_id': int(position_id),
                'symbol': entry_deal['symbol'],
                'trade_type': trade_type,
                'entry_time': entry_deal['time'],
                'entry_price': float(entry_deal['price']),
                'volume': float(entry_deal['volume']),
                'exit_time': exit_deal['time'] if exit_deal is not None else None,
                'exit_price': float(exit_deal['price']) if exit_deal is not None else None,
                'profit': float(position_profit),
                'commission': float(position_commission),
                'swap': float(position_swap),
                'magic_number': int(entry_deal['magic']) if pd.notna(entry_deal['magic']) else None,
                'comment': entry_deal['comment'] if pd.notna(entry_deal['comment']) else '',
            }

            trades.append(trade)

        trades_df = pd.DataFrame(trades)

        if not trades_df.empty:
            trades_df = trades_df.sort_values(['symbol', 'entry_time'])

        print(f"✅ Loaded {len(trades_df)} trades")
        return trades_df

    except Exception as e:
        print(f"❌ Error loading trades: {e}")
        return pd.DataFrame()


def detect_grid_sequences(trades_df):
    """Detect grid trading sequences"""
    grid_sequences = []

    for symbol in trades_df['symbol'].unique():
        symbol_trades = trades_df[trades_df['symbol'] == symbol].copy()
        symbol_trades = symbol_trades.sort_values('entry_time')

        i = 0
        while i < len(symbol_trades):
            current = symbol_trades.iloc[i]
            grid_trades = [current]

            # Look for consecutive same-direction trades
            j = i + 1
            while j < len(symbol_trades):
                next_trade = symbol_trades.iloc[j]
                time_diff = (next_trade['entry_time'] - current['entry_time']).total_seconds() / 3600

                if (next_trade['trade_type'] == current['trade_type'] and time_diff < 48):
                    grid_trades.append(next_trade)
                    j += 1
                else:
                    break

            if len(grid_trades) >= 2:
                prices = [t['entry_price'] for t in grid_trades]
                volumes = [t['volume'] for t in grid_trades]
                spacings = [abs(prices[k+1] - prices[k]) for k in range(len(prices)-1)]
                avg_spacing = np.mean(spacings) if spacings else 0
                spacing_std = np.std(spacings) if len(spacings) > 1 else 0

                # Check if volumes increase (martingale)
                is_martingale = all(volumes[k+1] >= volumes[k] for k in range(len(volumes)-1))
                volume_multiplier = volumes[-1] / volumes[0] if volumes[0] > 0 else 1

                total_profit = sum(t['profit'] for t in grid_trades)
                is_successful = total_profit > 0

                grid_sequences.append({
                    'type': 'GRID',
                    'symbol': symbol,
                    'direction': current['trade_type'],
                    'trades': grid_trades,
                    'count': len(grid_trades),
                    'avg_spacing': avg_spacing,
                    'spacing_std': spacing_std,
                    'is_regular_spacing': spacing_std < avg_spacing * 0.3 if avg_spacing > 0 else False,
                    'is_martingale': is_martingale,
                    'volume_multiplier': volume_multiplier,
                    'total_volume': sum(volumes),
                    'total_profit': total_profit,
                    'is_successful': is_successful,
                    'start_time': grid_trades[0]['entry_time'],
                    'end_time': grid_trades[-1]['exit_time'] if grid_trades[-1]['exit_time'] else datetime.now(),
                })

            i = j if j > i + 1 else i + 1

    return grid_sequences


def detect_hedge_pairs(trades_df):
    """Detect hedging patterns"""
    hedge_pairs = []

    for symbol in trades_df['symbol'].unique():
        symbol_trades = trades_df[trades_df['symbol'] == symbol].copy()
        symbol_trades = symbol_trades.sort_values('entry_time')

        for i in range(len(symbol_trades)):
            for j in range(i + 1, len(symbol_trades)):
                trade1 = symbol_trades.iloc[i]
                trade2 = symbol_trades.iloc[j]

                time_diff_minutes = (trade2['entry_time'] - trade1['entry_time']).total_seconds() / 60

                # Hedge if opposite directions within 60 minutes
                if (trade1['trade_type'] != trade2['trade_type'] and
                    time_diff_minutes < 60 and
                    abs(trade1['entry_price'] - trade2['entry_price']) < trade1['entry_price'] * 0.01):

                    volume_ratio = trade2['volume'] / trade1['volume'] if trade1['volume'] > 0 else 0

                    # Calculate underwater amount at time of hedge
                    if trade1['trade_type'] == 'buy':
                        underwater_pips = (trade1['entry_price'] - trade2['entry_price']) * 10000
                    else:
                        underwater_pips = (trade2['entry_price'] - trade1['entry_price']) * 10000

                    combined_profit = trade1.get('profit', 0) + trade2.get('profit', 0)

                    hedge_pairs.append({
                        'type': 'HEDGE',
                        'symbol': symbol,
                        'trade1': trade1,
                        'trade2': trade2,
                        'time_diff_minutes': time_diff_minutes,
                        'price_diff': abs(trade1['entry_price'] - trade2['entry_price']),
                        'underwater_pips': abs(underwater_pips),
                        'volume_ratio': volume_ratio,
                        'is_overhedge': volume_ratio > 1.5,
                        'combined_profit': combined_profit,
                        'is_successful': combined_profit > 0,
                    })

    return hedge_pairs


def detect_dca_sequences(trades_df):
    """Detect DCA/Martingale sequences"""
    dca_sequences = []

    for symbol in trades_df['symbol'].unique():
        symbol_trades = trades_df[trades_df['symbol'] == symbol].copy()
        symbol_trades = symbol_trades.sort_values('entry_time')

        i = 0
        while i < len(symbol_trades):
            current = symbol_trades.iloc[i]
            dca_trades = [current]

            j = i + 1
            while j < len(symbol_trades):
                next_trade = symbol_trades.iloc[j]
                time_diff = (next_trade['entry_time'] - current['entry_time']).total_seconds() / 3600

                if (next_trade['trade_type'] == current['trade_type'] and time_diff < 48):
                    # Check if adding to losing position
                    if current['trade_type'] == 'buy':
                        is_worse = next_trade['entry_price'] < current['entry_price']
                    else:
                        is_worse = next_trade['entry_price'] > current['entry_price']

                    if is_worse:
                        dca_trades.append(next_trade)
                    j += 1
                else:
                    break

            if len(dca_trades) >= 2:
                volumes = [t['volume'] for t in dca_trades]
                lot_multipliers = [volumes[k+1] / volumes[k] if volumes[k] > 0 else 1
                                  for k in range(len(volumes)-1)]
                avg_multiplier = np.mean(lot_multipliers) if lot_multipliers else 1

                prices = [t['entry_price'] for t in dca_trades]
                price_decline = abs(prices[-1] - prices[0])

                total_profit = sum(t.get('profit', 0) for t in dca_trades)

                # Calculate max drawdown
                max_volume = max(volumes)
                avg_entry = np.average(prices, weights=volumes)

                duration = (dca_trades[-1]['entry_time'] - dca_trades[0]['entry_time']).total_seconds() / 3600

                dca_sequences.append({
                    'type': 'DCA',
                    'symbol': symbol,
                    'direction': current['trade_type'],
                    'trades': dca_trades,
                    'count': len(dca_trades),
                    'avg_lot_multiplier': avg_multiplier,
                    'max_volume': max_volume,
                    'total_volume': sum(volumes),
                    'avg_entry_price': avg_entry,
                    'price_decline': price_decline,
                    'price_decline_pips': price_decline * 10000,
                    'total_profit': total_profit,
                    'is_successful': total_profit > 0,
                    'duration_hours': duration,
                })

            i = j if j > i + 1 else i + 1

    return dca_sequences


def analyze_timing_patterns(sequences):
    """Analyze timing patterns across sequences"""

    timing_stats = {
        'by_hour': defaultdict(lambda: {'count': 0, 'successful': 0, 'avg_profit': 0}),
        'by_day': defaultdict(lambda: {'count': 0, 'successful': 0, 'avg_profit': 0}),
        'by_duration': defaultdict(lambda: {'count': 0, 'successful': 0, 'avg_profit': 0}),
    }

    for seq in sequences:
        if 'start_time' in seq:
            hour = seq['start_time'].hour
            day = seq['start_time'].strftime('%A')

            timing_stats['by_hour'][hour]['count'] += 1
            if seq.get('is_successful'):
                timing_stats['by_hour'][hour]['successful'] += 1
            timing_stats['by_hour'][hour]['avg_profit'] += seq.get('total_profit', 0)

            timing_stats['by_day'][day]['count'] += 1
            if seq.get('is_successful'):
                timing_stats['by_day'][day]['successful'] += 1
            timing_stats['by_day'][day]['avg_profit'] += seq.get('total_profit', 0)

        if 'duration_hours' in seq:
            duration_bucket = f"{int(seq['duration_hours']//24)}d" if seq['duration_hours'] >= 24 else f"{int(seq['duration_hours'])}h"
            timing_stats['by_duration'][duration_bucket]['count'] += 1
            if seq.get('is_successful'):
                timing_stats['by_duration'][duration_bucket]['successful'] += 1
            timing_stats['by_duration'][duration_bucket]['avg_profit'] += seq.get('total_profit', 0)

    # Calculate averages
    for hour_stats in timing_stats['by_hour'].values():
        if hour_stats['count'] > 0:
            hour_stats['avg_profit'] /= hour_stats['count']
            hour_stats['success_rate'] = (hour_stats['successful'] / hour_stats['count']) * 100

    for day_stats in timing_stats['by_day'].values():
        if day_stats['count'] > 0:
            day_stats['avg_profit'] /= day_stats['count']
            day_stats['success_rate'] = (day_stats['successful'] / day_stats['count']) * 100

    for duration_stats in timing_stats['by_duration'].values():
        if duration_stats['count'] > 0:
            duration_stats['avg_profit'] /= duration_stats['count']
            duration_stats['success_rate'] = (duration_stats['successful'] / duration_stats['count']) * 100

    return timing_stats


def analyze_leverage_risk(sequences):
    """Analyze leverage and risk metrics"""

    risk_metrics = {
        'max_exposure': 0,
        'avg_exposure': 0,
        'max_drawdown_pips': 0,
        'sequences_by_risk': defaultdict(lambda: {'count': 0, 'successful': 0}),
    }

    exposures = []
    drawdowns = []

    for seq in sequences:
        total_volume = seq.get('total_volume', 0)
        exposures.append(total_volume)

        if 'price_decline_pips' in seq:
            drawdowns.append(seq['price_decline_pips'])

        # Categorize by risk level
        if total_volume < 0.1:
            risk_level = 'Low (<0.1 lots)'
        elif total_volume < 0.5:
            risk_level = 'Medium (0.1-0.5 lots)'
        elif total_volume < 1.0:
            risk_level = 'High (0.5-1.0 lots)'
        else:
            risk_level = 'Extreme (>1.0 lots)'

        risk_metrics['sequences_by_risk'][risk_level]['count'] += 1
        if seq.get('is_successful'):
            risk_metrics['sequences_by_risk'][risk_level]['successful'] += 1

    if exposures:
        risk_metrics['max_exposure'] = max(exposures)
        risk_metrics['avg_exposure'] = np.mean(exposures)

    if drawdowns:
        risk_metrics['max_drawdown_pips'] = max(drawdowns)

    # Calculate success rates
    for risk_level, stats in risk_metrics['sequences_by_risk'].items():
        if stats['count'] > 0:
            stats['success_rate'] = (stats['successful'] / stats['count']) * 100

    return risk_metrics


def main():
    """Main analysis function"""
    print("=" * 80)
    print("DEEP DIVE RECOVERY STRATEGY ANALYSIS")
    print("Hedging • DCA • Martingale • Timing • Leverage")
    print("=" * 80)

    # Load trades
    trades_df = load_trades_from_db()

    if trades_df.empty:
        print("\n❌ No trades found - cannot perform analysis")
        sys.exit(1)

    print(f"\n📊 Analyzing {len(trades_df)} trades...")

    # Detect all strategy patterns
    print("\n🔍 Detecting strategy patterns...")
    grid_sequences = detect_grid_sequences(trades_df)
    hedge_pairs = detect_hedge_pairs(trades_df)
    dca_sequences = detect_dca_sequences(trades_df)

    print(f"   Found {len(grid_sequences)} grid sequences")
    print(f"   Found {len(hedge_pairs)} hedge pairs")
    print(f"   Found {len(dca_sequences)} DCA sequences")

    # ========== GRID ANALYSIS ==========
    print("\n" + "=" * 80)
    print("📐 GRID TRADING ANALYSIS")
    print("=" * 80)

    if grid_sequences:
        successful_grids = [g for g in grid_sequences if g['is_successful']]
        martingale_grids = [g for g in grid_sequences if g['is_martingale']]

        print(f"\nTotal Grid Sequences: {len(grid_sequences)}")
        print(f"Successful: {len(successful_grids)} ({len(successful_grids)/len(grid_sequences)*100:.1f}%)")
        print(f"With Martingale: {len(martingale_grids)} ({len(martingale_grids)/len(grid_sequences)*100:.1f}%)")

        print(f"\nGrid Statistics:")
        avg_trades = np.mean([g['count'] for g in grid_sequences])
        avg_spacing = np.mean([g['avg_spacing'] for g in grid_sequences])
        avg_profit = np.mean([g['total_profit'] for g in grid_sequences])
        avg_volume_mult = np.mean([g['volume_multiplier'] for g in grid_sequences])

        print(f"  Avg trades per grid: {avg_trades:.1f}")
        print(f"  Avg price spacing: {avg_spacing:.5f} ({avg_spacing*10000:.1f} pips)")
        print(f"  Avg profit per grid: ${avg_profit:.2f}")
        print(f"  Avg volume multiplier: {avg_volume_mult:.2f}x")

        # Show top 5 most profitable grids
        print(f"\nTop 5 Most Profitable Grids:")
        sorted_grids = sorted(grid_sequences, key=lambda x: x['total_profit'], reverse=True)[:5]
        for idx, grid in enumerate(sorted_grids, 1):
            print(f"  {idx}. {grid['count']} trades, {grid['symbol']}, "
                  f"${grid['total_profit']:.2f}, "
                  f"Vol Mult: {grid['volume_multiplier']:.2f}x")

    else:
        print("\n⚠️  No grid sequences detected")

    # ========== HEDGE ANALYSIS ==========
    print("\n" + "=" * 80)
    print("⚖️  HEDGING ANALYSIS")
    print("=" * 80)

    if hedge_pairs:
        successful_hedges = [h for h in hedge_pairs if h['is_successful']]
        overhedges = [h for h in hedge_pairs if h['is_overhedge']]

        print(f"\nTotal Hedge Pairs: {len(hedge_pairs)}")
        print(f"Successful: {len(successful_hedges)} ({len(successful_hedges)/len(hedge_pairs)*100:.1f}%)")
        print(f"Overhedges (>1.5x): {len(overhedges)} ({len(overhedges)/len(hedge_pairs)*100:.1f}%)")

        print(f"\nHedge Statistics:")
        avg_time = np.mean([h['time_diff_minutes'] for h in hedge_pairs])
        avg_underwater = np.mean([h['underwater_pips'] for h in hedge_pairs])
        avg_ratio = np.mean([h['volume_ratio'] for h in hedge_pairs])
        avg_profit = np.mean([h['combined_profit'] for h in hedge_pairs])

        print(f"  Avg time to hedge: {avg_time:.1f} minutes")
        print(f"  Avg underwater at hedge: {avg_underwater:.1f} pips")
        print(f"  Avg hedge ratio: {avg_ratio:.2f}x")
        print(f"  Avg profit per pair: ${avg_profit:.2f}")

        # Analyze hedge timing
        print(f"\nHedge Trigger Analysis:")
        quick_hedges = len([h for h in hedge_pairs if h['time_diff_minutes'] < 10])
        medium_hedges = len([h for h in hedge_pairs if 10 <= h['time_diff_minutes'] < 30])
        slow_hedges = len([h for h in hedge_pairs if h['time_diff_minutes'] >= 30])

        print(f"  Quick (<10 min): {quick_hedges} hedges")
        print(f"  Medium (10-30 min): {medium_hedges} hedges")
        print(f"  Slow (>30 min): {slow_hedges} hedges")

        # Show most extreme hedges
        print(f"\nMost Extreme Hedge Scenarios:")
        sorted_hedges = sorted(hedge_pairs, key=lambda x: x['underwater_pips'], reverse=True)[:5]
        for idx, hedge in enumerate(sorted_hedges, 1):
            print(f"  {idx}. {hedge['symbol']}, "
                  f"{hedge['underwater_pips']:.1f} pips underwater, "
                  f"{hedge['volume_ratio']:.2f}x hedge, "
                  f"Result: ${hedge['combined_profit']:.2f}")

    else:
        print("\n⚠️  No hedge pairs detected")

    # ========== DCA/MARTINGALE ANALYSIS ==========
    print("\n" + "=" * 80)
    print("💰 DCA / MARTINGALE ANALYSIS")
    print("=" * 80)

    if dca_sequences:
        successful_dca = [d for d in dca_sequences if d['is_successful']]

        print(f"\nTotal DCA Sequences: {len(dca_sequences)}")
        print(f"Successful: {len(successful_dca)} ({len(successful_dca)/len(dca_sequences)*100:.1f}%)")

        print(f"\nDCA Statistics:")
        avg_levels = np.mean([d['count'] for d in dca_sequences])
        avg_multiplier = np.mean([d['avg_lot_multiplier'] for d in dca_sequences])
        avg_decline = np.mean([d['price_decline_pips'] for d in dca_sequences])
        avg_profit = np.mean([d['total_profit'] for d in dca_sequences])
        avg_duration = np.mean([d['duration_hours'] for d in dca_sequences])

        print(f"  Avg DCA levels: {avg_levels:.1f}")
        print(f"  Avg lot multiplier: {avg_multiplier:.2f}x")
        print(f"  Avg price decline: {avg_decline:.1f} pips")
        print(f"  Avg profit per sequence: ${avg_profit:.2f}")
        print(f"  Avg duration: {avg_duration:.1f} hours")

        # Success rate by number of levels
        print(f"\nSuccess Rate by DCA Depth:")
        for level in range(2, 8):
            level_sequences = [d for d in dca_sequences if d['count'] == level]
            if level_sequences:
                successful = len([d for d in level_sequences if d['is_successful']])
                success_rate = (successful / len(level_sequences)) * 100
                avg_profit_level = np.mean([d['total_profit'] for d in level_sequences])
                print(f"  {level} levels: {success_rate:.1f}% success rate "
                      f"({successful}/{len(level_sequences)}), "
                      f"Avg P/L: ${avg_profit_level:.2f}")

        # Show worst DCA scenarios
        print(f"\nWorst DCA Scenarios:")
        sorted_dca = sorted(dca_sequences, key=lambda x: x['total_profit'])[:5]
        for idx, dca in enumerate(sorted_dca, 1):
            print(f"  {idx}. {dca['count']} levels, {dca['symbol']}, "
                  f"{dca['price_decline_pips']:.1f} pips decline, "
                  f"${dca['total_profit']:.2f}, "
                  f"{dca['duration_hours']:.1f}h duration")

    else:
        print("\n⚠️  No DCA sequences detected")

    # ========== TIMING ANALYSIS ==========
    print("\n" + "=" * 80)
    print("⏰ TIMING ANALYSIS")
    print("=" * 80)

    all_sequences = grid_sequences + dca_sequences
    if all_sequences:
        timing_stats = analyze_timing_patterns(all_sequences)

        # Best hours
        print(f"\nBest Hours for Recovery Strategies:")
        sorted_hours = sorted(
            timing_stats['by_hour'].items(),
            key=lambda x: x[1]['success_rate'],
            reverse=True
        )[:5]
        for hour, stats in sorted_hours:
            if stats['count'] >= 3:
                print(f"  Hour {hour:02d}:00 - {stats['success_rate']:.1f}% success "
                      f"({stats['successful']}/{stats['count']}), "
                      f"Avg P/L: ${stats['avg_profit']:.2f}")

        # Best days
        print(f"\nBest Days for Recovery Strategies:")
        sorted_days = sorted(
            timing_stats['by_day'].items(),
            key=lambda x: x[1]['success_rate'],
            reverse=True
        )
        for day, stats in sorted_days:
            print(f"  {day}: {stats['success_rate']:.1f}% success "
                  f"({stats['successful']}/{stats['count']}), "
                  f"Avg P/L: ${stats['avg_profit']:.2f}")

    # ========== LEVERAGE & RISK ANALYSIS ==========
    print("\n" + "=" * 80)
    print("📊 LEVERAGE & RISK ANALYSIS")
    print("=" * 80)

    if all_sequences:
        risk_metrics = analyze_leverage_risk(all_sequences)

        print(f"\nExposure Metrics:")
        print(f"  Max total exposure: {risk_metrics['max_exposure']:.2f} lots")
        print(f"  Avg total exposure: {risk_metrics['avg_exposure']:.2f} lots")
        print(f"  Max drawdown: {risk_metrics['max_drawdown_pips']:.1f} pips")

        print(f"\nSuccess Rate by Risk Level:")
        for risk_level, stats in sorted(risk_metrics['sequences_by_risk'].items()):
            print(f"  {risk_level}: {stats['success_rate']:.1f}% "
                  f"({stats['successful']}/{stats['count']})")

    # ========== COMBINED STRATEGIES ==========
    print("\n" + "=" * 80)
    print("🔗 COMBINED STRATEGY ANALYSIS")
    print("=" * 80)

    # Find sequences that used both grid AND hedge
    combined_strategies = []
    for grid in grid_sequences:
        grid_symbols = [t['symbol'] for t in grid['trades']]
        grid_times = [(t['entry_time'], t.get('exit_time')) for t in grid['trades']]

        for hedge in hedge_pairs:
            if hedge['symbol'] == grid['symbol']:
                # Check if hedge occurred during grid
                hedge_time = hedge['trade2']['entry_time']
                if any(start <= hedge_time <= (end if end else datetime.now())
                       for start, end in grid_times):
                    combined_strategies.append({
                        'grid': grid,
                        'hedge': hedge,
                        'combined_profit': grid['total_profit'] + hedge['combined_profit']
                    })

    if combined_strategies:
        print(f"\nDetected {len(combined_strategies)} Grid+Hedge combinations")
        successful = len([c for c in combined_strategies if c['combined_profit'] > 0])
        print(f"Successful: {successful} ({successful/len(combined_strategies)*100:.1f}%)")

        print(f"\nTop Combined Strategies:")
        sorted_combined = sorted(combined_strategies,
                                key=lambda x: x['combined_profit'],
                                reverse=True)[:5]
        for idx, combo in enumerate(sorted_combined, 1):
            print(f"  {idx}. {combo['grid']['count']} grid trades + hedge, "
                  f"${combo['combined_profit']:.2f}")

    # ========== RECOMMENDATIONS ==========
    print("\n" + "=" * 80)
    print("💡 RECOMMENDATIONS")
    print("=" * 80)

    print("\n1. Grid Trading:")
    if grid_sequences:
        successful_pct = len([g for g in grid_sequences if g['is_successful']]) / len(grid_sequences) * 100
        if successful_pct > 60:
            print(f"   ✅ Grid strategy is working ({successful_pct:.1f}% success)")
            print(f"   → Maintain current grid spacing: ~{avg_spacing*10000:.1f} pips")
        else:
            print(f"   ⚠️  Grid strategy underperforming ({successful_pct:.1f}% success)")
            print(f"   → Consider wider spacing or reducing max levels")

    print("\n2. Hedging:")
    if hedge_pairs:
        successful_pct = len([h for h in hedge_pairs if h['is_successful']]) / len(hedge_pairs) * 100
        print(f"   Current success rate: {successful_pct:.1f}%")
        print(f"   Avg trigger point: {avg_underwater:.1f} pips underwater")
        if avg_ratio > 2.0:
            print(f"   ⚠️  Overhedging detected ({avg_ratio:.2f}x ratio)")
            print(f"   → Consider reducing hedge ratio to 1.5-2.0x")
        else:
            print(f"   ✅ Hedge ratio is reasonable ({avg_ratio:.2f}x)")

    print("\n3. DCA/Martingale:")
    if dca_sequences:
        # Find optimal depth
        best_depth = None
        best_rate = 0
        for level in range(2, 8):
            level_sequences = [d for d in dca_sequences if d['count'] == level]
            if len(level_sequences) >= 3:
                success_rate = len([d for d in level_sequences if d['is_successful']]) / len(level_sequences) * 100
                if success_rate > best_rate:
                    best_rate = success_rate
                    best_depth = level

        if best_depth:
            print(f"   → Optimal DCA depth: {best_depth} levels ({best_rate:.1f}% success)")
            print(f"   → Recommended lot multiplier: {avg_multiplier:.2f}x")
        else:
            print(f"   ⚠️  Insufficient data for recommendation")

    print("\n4. Timing:")
    if all_sequences and timing_stats['by_hour']:
        best_hour = max(timing_stats['by_hour'].items(),
                       key=lambda x: x[1]['success_rate'] if x[1]['count'] >= 3 else 0)
        if best_hour[1]['count'] >= 3:
            print(f"   → Best entry hour: {best_hour[0]:02d}:00 "
                  f"({best_hour[1]['success_rate']:.1f}% success)")

    print("\n5. Risk Management:")
    if risk_metrics['max_exposure'] > 1.0:
        print(f"   ⚠️  Max exposure very high: {risk_metrics['max_exposure']:.2f} lots")
        print(f"   → Consider implementing max exposure limit of 1.0 lot")
    else:
        print(f"   ✅ Exposure management acceptable")

    # Export detailed results
    print("\n" + "=" * 80)
    print("💾 EXPORTING RESULTS")
    print("=" * 80)

    results = {
        'analysis_date': datetime.now().isoformat(),
        'grid_sequences': len(grid_sequences),
        'hedge_pairs': len(hedge_pairs),
        'dca_sequences': len(dca_sequences),
        'risk_metrics': risk_metrics,
    }

    with open('recovery_strategy_analysis.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print("✅ Detailed results saved to: recovery_strategy_analysis.json")

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
