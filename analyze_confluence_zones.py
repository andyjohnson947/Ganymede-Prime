"""
Confluence Zone Analyzer
Identifies high-value overlapping trade setups from EA reverse engineering data
Now includes HTF (Higher Time Frame) multi-timeframe institutional markers
"""

import pandas as pd
import numpy as np
from collections import defaultdict
import json
from pathlib import Path


def load_htf_data(htf_json_file='multi_timeframe_analysis.json'):
    """
    Load HTF multi-timeframe analysis data

    Returns:
        dict with HTF levels or None if not available
    """
    htf_file = Path(htf_json_file)

    if not htf_file.exists():
        return None

    try:
        with open(htf_file, 'r') as f:
            htf_data = json.load(f)
        return htf_data
    except Exception as e:
        print(f"⚠️  Could not load HTF data: {e}")
        return None


def check_htf_confluence(trade, htf_data, tolerance_pct=0.3):
    """
    Check if trade aligns with HTF institutional markers

    Args:
        trade: Trade row from dataframe
        htf_data: HTF analysis data dict
        tolerance_pct: Price tolerance as percentage (0.3 = 0.3%)

    Returns:
        tuple: (score_addition, active_factors)
    """
    score = 0
    factors = []

    if not htf_data:
        return score, factors

    entry_price = trade.get('entry_price')
    if not entry_price or pd.isna(entry_price):
        return score, factors

    tolerance = entry_price * (tolerance_pct / 100)

    # Check Daily LVN/HVN levels
    daily_vp = htf_data.get('lvn_multi_timeframe', {}).get('D1', {})
    if daily_vp:
        # Check HVN levels (high volume = S/R)
        for hvn in daily_vp.get('hvn_levels', []):
            if abs(entry_price - hvn) < tolerance:
                score += 2  # HTF levels get higher weight
                factors.append('Daily HVN')
                break

        # Check LVN levels (low volume = breakout)
        for lvn in daily_vp.get('lvn_levels', []):
            if abs(entry_price - lvn) < tolerance:
                score += 1
                factors.append('Daily LVN')
                break

        # Check Daily POC/VAH/VAL
        if abs(entry_price - daily_vp.get('poc', 0)) < tolerance:
            score += 2
            factors.append('Daily POC')
        elif abs(entry_price - daily_vp.get('vah', 0)) < tolerance:
            score += 1
            factors.append('Daily VAH')
        elif abs(entry_price - daily_vp.get('val', 0)) < tolerance:
            score += 1
            factors.append('Daily VAL')

    # Check Weekly LVN/HVN levels
    weekly_vp = htf_data.get('lvn_multi_timeframe', {}).get('W1', {})
    if weekly_vp:
        # Check HVN levels
        for hvn in weekly_vp.get('hvn_levels', []):
            if abs(entry_price - hvn) < tolerance:
                score += 3  # Weekly gets even higher weight
                factors.append('Weekly HVN')
                break

        # Check LVN levels
        for lvn in weekly_vp.get('lvn_levels', []):
            if abs(entry_price - lvn) < tolerance:
                score += 2
                factors.append('Weekly LVN')
                break

        # Check Weekly POC
        if abs(entry_price - weekly_vp.get('poc', 0)) < tolerance:
            score += 3
            factors.append('Weekly POC')

    # Check Previous Week levels
    prev_week = htf_data.get('previous_week_levels', {})
    if prev_week:
        # Week High/Low
        if abs(entry_price - prev_week.get('high', 0)) < tolerance:
            score += 2
            factors.append('Prev Week High')
        elif abs(entry_price - prev_week.get('low', 0)) < tolerance:
            score += 2
            factors.append('Prev Week Low')

        # Week Open/Close
        if abs(entry_price - prev_week.get('open', 0)) < tolerance:
            score += 1
            factors.append('Prev Week Open')
        elif abs(entry_price - prev_week.get('close', 0)) < tolerance:
            score += 1
            factors.append('Prev Week Close')

        # VWAP Bands
        vwap_bands = prev_week.get('vwap_bands', {})
        if vwap_bands:
            vwap = vwap_bands.get('vwap', 0)
            if abs(entry_price - vwap) < tolerance:
                score += 2
                factors.append('Prev Week VWAP')
            elif abs(entry_price - vwap_bands.get('upper_2std', 0)) < tolerance:
                score += 2
                factors.append('Prev Week VWAP +2σ')
            elif abs(entry_price - vwap_bands.get('lower_2std', 0)) < tolerance:
                score += 2
                factors.append('Prev Week VWAP -2σ')

        # Swing Highs/Lows
        for swing_high in prev_week.get('swing_highs', []):
            if abs(entry_price - swing_high) < tolerance:
                score += 1
                factors.append('Prev Week Swing High')
                break

        for swing_low in prev_week.get('swing_lows', []):
            if abs(entry_price - swing_low) < tolerance:
                score += 1
                factors.append('Prev Week Swing Low')
                break

        # Previous Week Volume Profile
        week_vp = prev_week.get('volume_profile', {})
        if week_vp:
            for hvn in week_vp.get('hvn_levels', [])[:3]:
                if abs(entry_price - hvn) < tolerance:
                    score += 2
                    factors.append('Prev Week VP HVN')
                    break

    return score, factors


def analyze_confluence_zones(trades_data_csv='ea_reverse_engineering_detailed.csv',
                            htf_json_file='multi_timeframe_analysis.json'):
    """
    Analyze confluence zones from reverse engineering data
    Now includes HTF multi-timeframe institutional markers

    Args:
        trades_data_csv: Path to detailed trade analysis CSV
        htf_json_file: Path to HTF multi-timeframe analysis JSON

    Returns:
        dict with confluence analysis results
    """

    try:
        df = pd.read_csv(trades_data_csv)
    except FileNotFoundError:
        print(f"❌ File not found: {trades_data_csv}")
        print("   Run 'python reverse_engineer_ea.py' first to generate the data")
        return None

    print("=" * 80)
    print("CONFLUENCE ZONE ANALYSIS (with HTF Markers)")
    print("=" * 80)
    print()

    # Load HTF data
    htf_data = load_htf_data(htf_json_file)
    if htf_data:
        print("✅ HTF multi-timeframe data loaded successfully")
        print("   Including: Daily/Weekly LVN, HVN, POC, VWAP, Swing Points")
        print()
    else:
        print("⚠️  HTF data not found - using basic confluence only")
        print("   Run 'python analyze_multi_timeframe.py' first for full analysis")
        print()

    # Check available columns
    available_columns = set(df.columns)
    print(f"📊 Dataset contains {len(df)} trades with {len(available_columns)} fields")
    print()

    # Define confluence factors to check
    confluence_factors = {
        'vwap_bands': ['in_vwap_band_1', 'in_vwap_band_2'],
        'swing_levels': ['at_swing_high', 'at_swing_low'],
        'volume_profile': ['at_poc', 'above_vah', 'below_val'],
        'order_blocks': ['order_block_bullish', 'order_block_bearish'],
        'lvn': ['at_lvn'],
        'previous_day_levels': ['at_prev_poc', 'at_prev_vah', 'at_prev_val', 'at_prev_vwap', 'at_prev_lvn'],
        'fair_value_gaps': ['fair_value_gap_up', 'fair_value_gap_down'],
        'liquidity': ['liquidity_sweep'],
    }

    # Report which factors are available
    print("🔍 Checking for confluence factors:")
    factors_found = {}
    for category, fields in confluence_factors.items():
        found = [f for f in fields if f in available_columns]
        if found:
            factors_found[category] = found
            print(f"  ✓ {category}: {len(found)} fields available")
        else:
            print(f"  - {category}: not in dataset")
    print()

    # Calculate confluence score for each trade
    results = []

    for idx, trade in df.iterrows():
        score = 0
        active_factors = []

        # Check HTF markers first (if available)
        htf_score, htf_factors = check_htf_confluence(trade, htf_data)
        score += htf_score
        active_factors.extend(htf_factors)

        # Check VWAP bands
        if trade.get('in_vwap_band_1') == True or trade.get('in_vwap_band_2') == True:
            score += 1
            if trade.get('in_vwap_band_1') == True:
                active_factors.append('VWAP Band 1')
            else:
                active_factors.append('VWAP Band 2')

        # Check swing levels
        if trade.get('at_swing_high') == True:
            score += 1
            active_factors.append('Swing High')
        elif trade.get('at_swing_low') == True:
            score += 1
            active_factors.append('Swing Low')

        # Check volume profile
        if trade.get('at_poc') == True:
            score += 1
            active_factors.append('POC')
        if trade.get('above_vah') == True:
            score += 1
            active_factors.append('Above VAH')
        elif trade.get('below_val') == True:
            score += 1
            active_factors.append('Below VAL')

        # Check order blocks
        if trade.get('order_block_bullish') == True:
            score += 1
            active_factors.append('Bullish Order Block')
        elif trade.get('order_block_bearish') == True:
            score += 1
            active_factors.append('Bearish Order Block')

        # Check LVN
        if trade.get('at_lvn') == True:
            score += 1
            active_factors.append('LVN')

        # Check previous day levels (if available)
        if trade.get('at_prev_poc') == True:
            score += 1
            active_factors.append('Prev Day POC')
        if trade.get('at_prev_vah') == True:
            score += 1
            active_factors.append('Prev Day VAH')
        elif trade.get('at_prev_val') == True:
            score += 1
            active_factors.append('Prev Day VAL')
        if trade.get('at_prev_vwap') == True:
            score += 1
            active_factors.append('Prev Day VWAP')
        if trade.get('at_prev_lvn') == True:
            score += 1
            active_factors.append('Prev Day LVN')

        # Check fair value gaps (if available)
        if trade.get('fair_value_gap_up') == True:
            score += 1
            active_factors.append('Bullish FVG')
        elif trade.get('fair_value_gap_down') == True:
            score += 1
            active_factors.append('Bearish FVG')

        # Check liquidity sweeps (if available)
        if trade.get('liquidity_sweep') == True:
            score += 1
            active_factors.append('Liquidity Sweep')

        if score > 0:
            results.append({
                'confluence_score': score,
                'factors': active_factors,
                'entry_time': trade.get('entry_time'),
                'entry_price': trade.get('entry_price'),
                'trade_type': trade.get('trade_type'),
                'profit': trade.get('profit'),
                'vwap_distance_pct': trade.get('vwap_distance_pct'),
            })

    # Convert to DataFrame for analysis
    confluence_df = pd.DataFrame(results)

    # Summary statistics
    print("📊 CONFLUENCE DISTRIBUTION")
    print("-" * 80)

    total_trades = len(confluence_df)
    print(f"Total Trades Analyzed: {total_trades}")
    print()

    # Count by confluence score
    score_counts = confluence_df['confluence_score'].value_counts().sort_index()
    for score, count in score_counts.items():
        pct = (count / total_trades * 100) if total_trades > 0 else 0
        print(f"  Confluence Score {score}: {count} trades ({pct:.1f}%)")
    print()

    # Win rate by confluence score
    print("🎯 WIN RATE BY CONFLUENCE LEVEL")
    print("-" * 80)

    # Filter only closed trades with profit data
    closed_trades = confluence_df[confluence_df['profit'].notna()].copy()

    if len(closed_trades) > 0:
        for score in sorted(closed_trades['confluence_score'].unique()):
            score_trades = closed_trades[closed_trades['confluence_score'] == score]
            winners = len(score_trades[score_trades['profit'] > 0])
            win_rate = (winners / len(score_trades) * 100) if len(score_trades) > 0 else 0
            avg_profit = score_trades['profit'].mean()

            print(f"  Score {score}: {win_rate:.1f}% win rate | Avg P/L: ${avg_profit:.2f} | {len(score_trades)} trades")
        print()
    else:
        print("  ⚠️ No closed trades with profit data found")
        print()

    # High-value confluence zones (3+ factors)
    high_value = confluence_df[confluence_df['confluence_score'] >= 3]

    if len(high_value) > 0:
        print(f"✨ HIGH-VALUE CONFLUENCE ZONES (Score ≥3)")
        print("-" * 80)
        print(f"Total High-Value Setups: {len(high_value)}")
        print()

        # Show top 10 examples
        high_value_sorted = high_value.sort_values('confluence_score', ascending=False)

        print("Top 10 Examples:")
        print()

        for idx, (_, trade) in enumerate(high_value_sorted.head(10).iterrows(), 1):
            profit_str = f"${trade['profit']:.2f}" if pd.notna(trade['profit']) else "OPEN"
            factors_str = " + ".join(trade['factors'])

            print(f"  {idx}. Score {trade['confluence_score']}: {trade['trade_type'].upper()}")
            print(f"     Time: {trade['entry_time']}")
            print(f"     Price: {trade['entry_price']:.5f}")
            print(f"     Factors: {factors_str}")
            print(f"     VWAP Deviation: {trade['vwap_distance_pct']:+.2f}%" if pd.notna(trade['vwap_distance_pct']) else "     VWAP Deviation: N/A")
            print(f"     P/L: {profit_str}")
            print()
    else:
        print("⚠️ No high-value confluence zones (3+ factors) detected")
        print()

    # Factor popularity
    print("📊 MOST COMMON FACTOR COMBINATIONS")
    print("-" * 80)

    factor_combinations = defaultdict(int)
    for factors in confluence_df['factors']:
        combo = tuple(sorted(factors))
        factor_combinations[combo] += 1

    # Sort by frequency
    sorted_combos = sorted(factor_combinations.items(), key=lambda x: x[1], reverse=True)

    print("Top 10 Factor Combinations:")
    print()

    for idx, (combo, count) in enumerate(sorted_combos[:10], 1):
        combo_str = " + ".join(combo)
        pct = (count / total_trades * 100) if total_trades > 0 else 0
        print(f"  {idx}. {combo_str}")
        print(f"     Frequency: {count} trades ({pct:.1f}%)")
        print()

    # Individual factor frequency
    print("📊 INDIVIDUAL FACTOR FREQUENCY")
    print("-" * 80)

    all_factors = []
    for factors in confluence_df['factors']:
        all_factors.extend(factors)

    factor_counts = pd.Series(all_factors).value_counts()

    for factor, count in factor_counts.items():
        pct = (count / total_trades * 100) if total_trades > 0 else 0
        print(f"  {factor}: {count} trades ({pct:.1f}%)")
    print()

    # Recommendations
    print("💡 RECOMMENDATIONS FOR PYTHON PLATFORM")
    print("-" * 80)

    # Calculate average win rate for high confluence
    if len(closed_trades) > 0:
        high_conf_closed = closed_trades[closed_trades['confluence_score'] >= 3]
        if len(high_conf_closed) > 0:
            high_conf_wr = len(high_conf_closed[high_conf_closed['profit'] > 0]) / len(high_conf_closed) * 100

            low_conf_closed = closed_trades[closed_trades['confluence_score'] <= 2]
            low_conf_wr = len(low_conf_closed[low_conf_closed['profit'] > 0]) / len(low_conf_closed) * 100 if len(low_conf_closed) > 0 else 0

            print(f"1. Require minimum confluence score of 3")
            print(f"   → High confluence (≥3): {high_conf_wr:.1f}% win rate")
            print(f"   → Low confluence (≤2): {low_conf_wr:.1f}% win rate")
            print(f"   → Improvement: +{high_conf_wr - low_conf_wr:.1f}%")
            print()

        # Most profitable combinations
        print("2. Prioritize these factor combinations:")
        for combo, count in sorted_combos[:3]:
            combo_str = " + ".join(combo)
            print(f"   → {combo_str}")
        print()

        # Most common single factors
        print("3. Key factors to always check:")
        for factor, count in list(factor_counts.items())[:3]:
            print(f"   → {factor} (appears in {count} setups)")
        print()

    print("4. Implementation priorities:")
    if htf_data:
        print("   → **HTF Markers: Daily/Weekly HVN, POC, Previous Week levels (HIGHEST PRIORITY)**")
    print("   → Primary: VWAP bands (most common)")
    print("   → Secondary: Volume Profile (POC/VAH/VAL)")
    print("   → Tertiary: Swing levels and order blocks")
    print()

    if htf_data:
        print("5. HTF Marker Benefits:")
        print("   → Weekly HVN/POC: +3 points each (institutional levels)")
        print("   → Daily HVN: +2 points (strong S/R zones)")
        print("   → Previous Week VWAP ±2σ: +2 points (reversal zones)")
        print("   → HTF levels carry MORE weight than intraday factors")
        print()

    # Export detailed results
    output_file = 'confluence_zones_detailed.csv'
    confluence_df.to_csv(output_file, index=False)
    print(f"✅ Detailed results exported to: {output_file}")
    print()

    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

    return {
        'total_trades': total_trades,
        'score_distribution': score_counts.to_dict(),
        'high_value_zones': len(high_value),
        'factor_combinations': dict(sorted_combos),
        'factor_frequency': factor_counts.to_dict(),
    }


if __name__ == '__main__':
    import sys

    csv_file = sys.argv[1] if len(sys.argv) > 1 else 'ea_reverse_engineering_detailed.csv'

    print(f"Analyzing confluence zones from: {csv_file}")
    print()

    results = analyze_confluence_zones(csv_file)

    if results:
        print()
        print("Next steps:")
        print("1. Review confluence_zones_detailed.csv")
        print("2. Implement high-score setups in your Python platform")
        print("3. Backtest with minimum confluence threshold of 3")
