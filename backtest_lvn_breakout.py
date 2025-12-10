#!/usr/bin/env python3
"""
Backtest: VWAP-Supported LVN Breakout Strategy
Uses existing confluence data to test breakout performance in trending markets

Strategy Logic:
1. Price near LVN (Low Volume Node) - low resistance area
2. Trending market (ADX >= 25) - momentum present
3. VWAP directional support (above VWAP = long, below = short)
4. Volume expansion (optional enhancement)
5. Entry: Break through LVN in direction of VWAP bias
"""

import pandas as pd
import numpy as np
from pathlib import Path
from analyze_by_adx_regime import calculate_adx_from_price


def detect_lvn_breakout_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect LVN breakout opportunities using confluence factors

    Confluence Factors:
    1. At or near LVN (low resistance)
    2. ADX >= 25 (trending)
    3. VWAP directional bias (price position vs VWAP)
    4. Volume expansion (> average)
    5. Moving away from POC (breaking out of consolidation)

    Args:
        df: DataFrame with all confluence data

    Returns:
        DataFrame with breakout signals and scores
    """

    signals = []

    for idx, row in df.iterrows():
        signal = {
            'entry_time': row['entry_time'],
            'entry_price': row['entry_price'],
            'direction': None,
            'confluence_score': 0,
            'factors': [],
            'actual_direction': row['trade_type'],
            'actual_profit': row['profit'],
            'actual_win': row['win'],
        }

        # Skip if missing critical data
        if pd.isna(row.get('adx')) or pd.isna(row.get('lvn_price')):
            continue

        adx = row['adx']
        at_lvn = row.get('at_lvn', False)
        lvn_percentile = row.get('lvn_percentile', 50)
        low_volume_area = row.get('low_volume_area', False)
        above_vwap = row.get('above_vwap', False)
        vwap_distance_pct = abs(row.get('vwap_distance_pct', 0))
        volume_percentile = row.get('volume_percentile', 50)
        at_poc = row.get('at_poc', False)

        # FILTER 1: Must be trending market (ADX >= 25)
        if adx < 25:
            continue

        # CONFLUENCE SCORING for LVN Breakout

        # Factor 1: Near LVN (low resistance area) - CRITICAL
        if at_lvn or low_volume_area:
            signal['confluence_score'] += 3  # High weight
            signal['factors'].append(f'at_lvn')
        elif lvn_percentile < 30:  # Near LVN area
            signal['confluence_score'] += 2
            signal['factors'].append(f'near_lvn')

        # Factor 2: ADX strength (trending confirmation)
        if adx >= 35:
            signal['confluence_score'] += 2
            signal['factors'].append(f'strong_trend_adx_{adx:.1f}')
        elif adx >= 25:
            signal['confluence_score'] += 1
            signal['factors'].append(f'trending_adx_{adx:.1f}')

        # Factor 3: VWAP directional bias - CRITICAL
        if above_vwap:
            # Price above VWAP = bullish bias
            signal['direction'] = 'buy'
            if vwap_distance_pct > 0.001:  # At least 0.1% above VWAP
                signal['confluence_score'] += 2
                signal['factors'].append('vwap_bullish_bias')
            else:
                signal['confluence_score'] += 1
                signal['factors'].append('vwap_neutral_bullish')
        else:
            # Price below VWAP = bearish bias
            signal['direction'] = 'sell'
            if vwap_distance_pct > 0.001:  # At least 0.1% below VWAP
                signal['confluence_score'] += 2
                signal['factors'].append('vwap_bearish_bias')
            else:
                signal['confluence_score'] += 1
                signal['factors'].append('vwap_neutral_bearish')

        # Factor 4: Volume expansion (breakout confirmation)
        if volume_percentile >= 70:
            signal['confluence_score'] += 2
            signal['factors'].append(f'high_volume_{volume_percentile:.0f}th')
        elif volume_percentile >= 50:
            signal['confluence_score'] += 1
            signal['factors'].append(f'above_avg_volume')

        # Factor 5: Away from POC (not stuck in consolidation)
        if not at_poc:
            signal['confluence_score'] += 1
            signal['factors'].append('away_from_poc')

        # Factor 6: VWAP band position (additional context)
        if row.get('in_vwap_band_2') or row.get('in_vwap_band_3'):
            signal['confluence_score'] += 1
            signal['factors'].append('vwap_outer_band')

        # Only keep signals with minimum confluence
        if signal['confluence_score'] >= 4:
            signals.append(signal)

    return pd.DataFrame(signals)


def evaluate_breakout_performance(signals_df: pd.DataFrame) -> dict:
    """
    Evaluate how the LVN breakout signals would have performed

    Args:
        signals_df: DataFrame with detected signals

    Returns:
        Performance metrics dict
    """

    if len(signals_df) == 0:
        return {
            'total_signals': 0,
            'trades_taken': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
            'total_profit': 0,
            'avg_profit': 0,
        }

    # Check if signal direction matched actual trade direction
    signals_df['direction_match'] = (
        ((signals_df['direction'] == 'buy') & (signals_df['actual_direction'].str.lower() == 'buy')) |
        ((signals_df['direction'] == 'sell') & (signals_df['actual_direction'].str.lower() == 'sell'))
    )

    # Only count trades where our signal matched the actual direction
    matched_trades = signals_df[signals_df['direction_match']].copy()

    if len(matched_trades) == 0:
        return {
            'total_signals': len(signals_df),
            'trades_taken': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
            'total_profit': 0,
            'avg_profit': 0,
        }

    wins = matched_trades['actual_win'].sum()
    losses = len(matched_trades) - wins
    win_rate = (wins / len(matched_trades)) * 100
    total_profit = matched_trades['actual_profit'].sum()
    avg_profit = matched_trades['actual_profit'].mean()

    # Performance by confluence score
    score_performance = {}
    for score in sorted(matched_trades['confluence_score'].unique()):
        score_trades = matched_trades[matched_trades['confluence_score'] == score]
        score_wins = score_trades['actual_win'].sum()
        score_wr = (score_wins / len(score_trades)) * 100 if len(score_trades) > 0 else 0
        score_profit = score_trades['actual_profit'].sum()

        score_performance[score] = {
            'trades': len(score_trades),
            'wins': score_wins,
            'losses': len(score_trades) - score_wins,
            'win_rate': score_wr,
            'total_profit': score_profit,
            'avg_profit': score_profit / len(score_trades),
        }

    return {
        'total_signals': len(signals_df),
        'trades_taken': len(matched_trades),
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'total_profit': total_profit,
        'avg_profit': avg_profit,
        'avg_win': matched_trades[matched_trades['actual_win']]['actual_profit'].mean() if wins > 0 else 0,
        'avg_loss': matched_trades[~matched_trades['actual_win']]['actual_profit'].mean() if losses > 0 else 0,
        'score_performance': score_performance,
        'matched_trades': matched_trades,
    }


def backtest_lvn_breakout(csv_path: str):
    """
    Main backtest function for LVN Breakout strategy
    """

    print("=" * 80)
    print("LVN BREAKOUT STRATEGY BACKTEST")
    print("VWAP-Supported Breakouts in Trending Markets")
    print("=" * 80)
    print()

    # Load data
    df = pd.read_csv(csv_path)
    print(f"📊 Total trades in dataset: {len(df)}")
    print()

    # Calculate profit if needed
    if 'profit' not in df.columns:
        if 'close_price' in df.columns and 'open_price' in df.columns:
            df['profit'] = np.where(
                df['type'].str.lower() == 'buy',
                df['close_price'] - df['open_price'],
                df['open_price'] - df['close_price']
            )
            if 'volume' in df.columns:
                df['profit'] = df['profit'] * df['volume'] * 100000
        elif 'exit_price' in df.columns and 'entry_price' in df.columns:
            df['profit'] = np.where(
                df['trade_type'].str.lower() == 'buy',
                df['exit_price'] - df['entry_price'],
                df['entry_price'] - df['exit_price']
            )
            if 'volume' in df.columns:
                df['profit'] = df['profit'] * df['volume'] * 100000

    df['win'] = df['profit'] > 0

    # Calculate ADX if not present
    if 'adx' not in df.columns:
        print("⚠️  Calculating ADX from price data...")
        df = calculate_adx_from_price(df)
        print(f"✅ ADX calculated (range: {df['adx'].min():.1f} - {df['adx'].max():.1f})")
        print()

    # Filter to trending markets only (ADX >= 25)
    trending_df = df[df['adx'] >= 25].copy()
    print(f"📈 Trending market trades (ADX >= 25): {len(trending_df)}")
    print(f"   ({len(trending_df)/len(df)*100:.1f}% of all trades)")
    print()

    # Detect LVN breakout signals
    print("🔍 Detecting LVN breakout signals...")
    signals_df = detect_lvn_breakout_signals(df)
    print(f"✅ Found {len(signals_df)} potential LVN breakout opportunities")
    print()

    # Evaluate performance
    print("=" * 80)
    print("BACKTEST RESULTS")
    print("=" * 80)
    print()

    results = evaluate_breakout_performance(signals_df)

    print(f"Total Signals Detected: {results['total_signals']}")
    print(f"Trades Taken (direction match): {results['trades_taken']}")
    print()

    if results['trades_taken'] > 0:
        print(f"📊 PERFORMANCE METRICS:")
        print(f"   Win Rate: {results['win_rate']:.1f}% ({results['wins']}W / {results['losses']}L)")
        print(f"   Total P/L: ${results['total_profit']:.2f}")
        print(f"   Avg Profit/Trade: ${results['avg_profit']:.2f}")
        print(f"   Avg Win: ${results['avg_win']:.2f}")
        print(f"   Avg Loss: ${results['avg_loss']:.2f}")

        if results['avg_loss'] != 0:
            rr_ratio = abs(results['avg_win'] / results['avg_loss'])
            print(f"   Risk/Reward: 1:{rr_ratio:.2f}")
        print()

        # Performance by confluence score
        print("=" * 80)
        print("PERFORMANCE BY CONFLUENCE SCORE")
        print("=" * 80)
        print()

        for score, perf in sorted(results['score_performance'].items()):
            print(f"Score {score}:")
            print(f"   Trades: {perf['trades']}")
            print(f"   Win Rate: {perf['win_rate']:.1f}% ({perf['wins']}W / {perf['losses']}L)")
            print(f"   Total P/L: ${perf['total_profit']:.2f}")
            print(f"   Avg P/L: ${perf['avg_profit']:.2f}")
            print()

        # Comparison to mean reversion in trending markets
        print("=" * 80)
        print("COMPARISON: LVN Breakout vs Mean Reversion (Trending Markets)")
        print("=" * 80)
        print()

        # Mean reversion performance in trending markets
        trending_mr = trending_df.copy()
        mr_wins = trending_mr['win'].sum()
        mr_win_rate = (mr_wins / len(trending_mr)) * 100
        mr_total_profit = trending_mr['profit'].sum()
        mr_avg_profit = trending_mr['profit'].mean()

        print(f"Mean Reversion (ADX >= 25):")
        print(f"   Trades: {len(trending_mr)}")
        print(f"   Win Rate: {mr_win_rate:.1f}%")
        print(f"   Total P/L: ${mr_total_profit:.2f}")
        print(f"   Avg P/L: ${mr_avg_profit:.2f}")
        print()

        print(f"LVN Breakout (ADX >= 25):")
        print(f"   Trades: {results['trades_taken']}")
        print(f"   Win Rate: {results['win_rate']:.1f}%")
        print(f"   Total P/L: ${results['total_profit']:.2f}")
        print(f"   Avg P/L: ${results['avg_profit']:.2f}")
        print()

        # Calculate improvement
        if results['trades_taken'] > 0:
            # Normalize by number of trades for fair comparison
            mr_profit_per_trade = mr_avg_profit
            bo_profit_per_trade = results['avg_profit']

            improvement = bo_profit_per_trade - mr_profit_per_trade
            improvement_pct = (improvement / abs(mr_profit_per_trade)) * 100 if mr_profit_per_trade != 0 else 0

            print(f"💡 IMPROVEMENT:")
            print(f"   Per-Trade P/L Change: ${improvement:+.2f} ({improvement_pct:+.1f}%)")

            if improvement > 0:
                print(f"   ✅ LVN Breakout performs BETTER in trending markets")
            else:
                print(f"   ⚠️  Mean reversion actually performed better")
            print()

        # Show example signals
        print("=" * 80)
        print("EXAMPLE LVN BREAKOUT SIGNALS (Top 5 by Confluence)")
        print("=" * 80)
        print()

        top_signals = results['matched_trades'].nlargest(5, 'confluence_score')
        for idx, signal in top_signals.iterrows():
            win_status = "✅ WIN" if signal['actual_win'] else "❌ LOSS"
            print(f"{win_status} | Score: {signal['confluence_score']} | "
                  f"{signal['direction'].upper()} @ {signal['entry_price']:.5f} | "
                  f"P/L: ${signal['actual_profit']:.2f}")
            print(f"   Factors: {', '.join(signal['factors'])}")
            print()

    else:
        print("⚠️  No signals matched actual trade directions")
        print("   This might indicate:")
        print("   - LVN breakout opportunities were not taken by the original EA")
        print("   - Different entry logic needed")
        print()

    # Recommendations
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print()

    if results['trades_taken'] > 0 and results['win_rate'] > 55:
        print("✅ STRONG PERFORMANCE - LVN Breakout strategy validated!")
        print()
        print("🎯 Next Steps:")
        print("   1. Implement breakout_detector.py with LVN logic")
        print("   2. Add volume_analyzer.py for expansion detection")
        print("   3. Create strategy_router.py to switch based on ADX")
        print("   4. Paper trade alongside mean reversion (no changes to reversion)")
    elif results['trades_taken'] > 0:
        print("📊 MODERATE PERFORMANCE - Further optimization needed")
        print()
        print("🎯 Next Steps:")
        print("   1. Adjust confluence weights")
        print("   2. Test different ADX thresholds")
        print("   3. Add additional filters (candle patterns, etc.)")
    else:
        print("⚠️  INSUFFICIENT DATA - Not enough matching signals")
        print()
        print("💡 Alternative Approach:")
        print("   - Create synthetic breakout opportunities from price data")
        print("   - Test on different timeframe data")
        print("   - Analyze LVN areas more broadly")


if __name__ == "__main__":
    csv_path = "ea_reverse_engineering_detailed.csv"

    if not Path(csv_path).exists():
        print(f"❌ Error: {csv_path} not found")
        print(f"   Looking in: {Path.cwd()}")
        exit(1)

    backtest_lvn_breakout(csv_path)
