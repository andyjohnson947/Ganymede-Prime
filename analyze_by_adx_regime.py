#!/usr/bin/env python3
"""
Analyze EA Trades by ADX Regime
Validates the breakout module concept by showing performance in trending vs ranging markets
"""

import pandas as pd
import numpy as np
from pathlib import Path


def calculate_adx_from_price(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate ADX from OHLC data

    Args:
        df: DataFrame with bar_high, bar_low, bar_close columns
        period: ADX period (default 14)

    Returns:
        DataFrame with adx, plus_di, minus_di columns added
    """
    high = df['bar_high'].values
    low = df['bar_low'].values
    close = df['bar_close'].values

    # Calculate True Range components
    tr1 = high[1:] - low[1:]
    tr2 = np.abs(high[1:] - close[:-1])
    tr3 = np.abs(low[1:] - close[:-1])

    # True Range is the maximum of the three
    tr = np.maximum(tr1, np.maximum(tr2, tr3))

    # Directional Movement
    up_move = high[1:] - high[:-1]
    down_move = low[:-1] - low[1:]

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    # Smoothed TR and DM using Wilder's smoothing (exponential moving average)
    alpha = 1.0 / period

    atr = np.zeros(len(tr))
    atr[period - 1] = tr[:period].mean()
    for i in range(period, len(tr)):
        atr[i] = atr[i - 1] * (1 - alpha) + tr[i] * alpha

    smoothed_plus_dm = np.zeros(len(plus_dm))
    smoothed_plus_dm[period - 1] = plus_dm[:period].mean()
    for i in range(period, len(plus_dm)):
        smoothed_plus_dm[i] = smoothed_plus_dm[i - 1] * (1 - alpha) + plus_dm[i] * alpha

    smoothed_minus_dm = np.zeros(len(minus_dm))
    smoothed_minus_dm[period - 1] = minus_dm[:period].mean()
    for i in range(period, len(minus_dm)):
        smoothed_minus_dm[i] = smoothed_minus_dm[i - 1] * (1 - alpha) + minus_dm[i] * alpha

    # Directional Indicators
    plus_di = np.zeros(len(atr))
    minus_di = np.zeros(len(atr))

    # Avoid division by zero
    valid = atr > 0
    plus_di[valid] = 100 * smoothed_plus_dm[valid] / atr[valid]
    minus_di[valid] = 100 * smoothed_minus_dm[valid] / atr[valid]

    # Directional Index (DX)
    di_sum = plus_di + minus_di
    di_diff = np.abs(plus_di - minus_di)

    dx = np.zeros(len(plus_di))
    valid_sum = di_sum > 0
    dx[valid_sum] = 100 * di_diff[valid_sum] / di_sum[valid_sum]

    # ADX (smoothed DX)
    adx = np.zeros(len(dx))
    adx[period - 1] = dx[:period].mean()
    for i in range(period, len(dx)):
        adx[i] = adx[i - 1] * (1 - alpha) + dx[i] * alpha

    # Pad with NaN for the first row (lost due to differencing)
    adx_padded = np.concatenate([[np.nan], adx])
    plus_di_padded = np.concatenate([[np.nan], plus_di])
    minus_di_padded = np.concatenate([[np.nan], minus_di])

    df['adx'] = adx_padded
    df['plus_di'] = plus_di_padded
    df['minus_di'] = minus_di_padded

    # Fill NaN values with forward fill
    df['adx'].fillna(method='bfill', inplace=True)
    df['plus_di'].fillna(method='bfill', inplace=True)
    df['minus_di'].fillna(method='bfill', inplace=True)

    return df


def analyze_by_adx_regime(csv_path: str):
    """
    Analyze trade performance split by ADX regime

    Shows:
    1. Mean reversion performance in ranging markets (ADX < 25)
    2. Mean reversion performance in trending markets (ADX >= 25)
    3. Opportunities currently being missed in trending conditions
    """

    print("=" * 80)
    print("ADX REGIME ANALYSIS - Validating Breakout Module Concept")
    print("=" * 80)
    print()

    # Load data
    df = pd.read_csv(csv_path)

    print(f"📊 Total trades analyzed: {len(df)}")
    print()

    # Calculate profit/loss
    if 'profit' not in df.columns:
        if 'close_price' in df.columns and 'open_price' in df.columns:
            df['profit'] = np.where(
                df['type'].str.lower() == 'buy',
                df['close_price'] - df['open_price'],
                df['open_price'] - df['close_price']
            )
            if 'volume' in df.columns:
                df['profit'] = df['profit'] * df['volume'] * 100000  # Convert to dollars
        else:
            print("⚠️  Cannot calculate profit - missing price columns")
            return

    df['win'] = df['profit'] > 0

    # Check if ADX column exists, if not calculate it
    if 'adx' not in df.columns:
        print("⚠️  No ADX column found - calculating from price data...")
        print()

        # Check if we have the necessary price columns
        required_cols = ['bar_high', 'bar_low', 'bar_close']
        if not all(col in df.columns for col in required_cols):
            print("❌ Cannot calculate ADX - missing required columns")
            print("   Need: bar_high, bar_low, bar_close")
            return

        # Calculate ADX
        df = calculate_adx_from_price(df)
        print(f"✅ ADX calculated for {len(df)} trades")
        print(f"   ADX range: {df['adx'].min():.1f} - {df['adx'].max():.1f}")
        print(f"   ADX mean: {df['adx'].mean():.1f}")
        print()

    # Define regimes
    df['regime'] = pd.cut(
        df['adx'],
        bins=[0, 20, 25, 40, 100],
        labels=['Strong Ranging', 'Weak Ranging', 'Trending', 'Strong Trending']
    )

    print("=" * 80)
    print("MARKET REGIME DISTRIBUTION")
    print("=" * 80)
    print()

    regime_dist = df['regime'].value_counts()
    for regime, count in regime_dist.items():
        pct = (count / len(df)) * 100
        print(f"  {regime:20s}: {count:3d} trades ({pct:5.1f}%)")

    print()
    print("=" * 80)
    print("PERFORMANCE BY ADX REGIME")
    print("=" * 80)
    print()

    # Analyze each regime
    for regime in ['Strong Ranging', 'Weak Ranging', 'Trending', 'Strong Trending']:
        regime_trades = df[df['regime'] == regime]

        if len(regime_trades) == 0:
            continue

        wins = regime_trades['win'].sum()
        losses = len(regime_trades) - wins
        win_rate = (wins / len(regime_trades)) * 100

        avg_win = regime_trades[regime_trades['win']]['profit'].mean() if wins > 0 else 0
        avg_loss = regime_trades[~regime_trades['win']]['profit'].mean() if losses > 0 else 0
        avg_profit = regime_trades['profit'].mean()
        total_profit = regime_trades['profit'].sum()

        avg_adx = regime_trades['adx'].mean()

        print(f"📊 {regime} (ADX avg: {avg_adx:.1f})")
        print(f"   Trades: {len(regime_trades)}")
        print(f"   Win Rate: {win_rate:.1f}% ({wins}W / {losses}L)")
        print(f"   Avg Win: ${avg_win:.2f}")
        print(f"   Avg Loss: ${avg_loss:.2f}")
        print(f"   Avg Profit/Trade: ${avg_profit:.2f}")
        print(f"   Total P/L: ${total_profit:.2f}")

        if avg_loss != 0:
            rr_ratio = abs(avg_win / avg_loss)
            print(f"   Risk/Reward: 1:{rr_ratio:.2f}")

        print()

    print("=" * 80)
    print("MEAN REVERSION vs BREAKOUT OPPORTUNITY")
    print("=" * 80)
    print()

    # Split at ADX = 25
    ranging = df[df['adx'] < 25]
    trending = df[df['adx'] >= 25]

    print("RANGING MARKETS (ADX < 25) - Mean Reversion IDEAL")
    print("-" * 80)
    if len(ranging) > 0:
        wins = ranging['win'].sum()
        win_rate = (wins / len(ranging)) * 100
        avg_profit = ranging['profit'].mean()
        total_profit = ranging['profit'].sum()

        print(f"  Trades: {len(ranging)} ({len(ranging)/len(df)*100:.1f}% of all trades)")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Avg Profit/Trade: ${avg_profit:.2f}")
        print(f"  Total P/L: ${total_profit:.2f}")
        print()

    print("TRENDING MARKETS (ADX >= 25) - BREAKOUT OPPORTUNITY")
    print("-" * 80)
    if len(trending) > 0:
        wins = trending['win'].sum()
        win_rate = (wins / len(trending)) * 100
        avg_profit = trending['profit'].mean()
        total_profit = trending['profit'].sum()

        print(f"  Trades: {len(trending)} ({len(trending)/len(df)*100:.1f}% of all trades)")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Avg Profit/Trade: ${avg_profit:.2f}")
        print(f"  Total P/L: ${total_profit:.2f}")
        print()

        if win_rate < 50:
            print("  ⚠️  POOR PERFORMANCE - Mean reversion struggles in trending markets")
            print("  💡 OPPORTUNITY: Breakout strategy could capture these trends instead")
        else:
            print("  ✅ GOOD PERFORMANCE - Current EA handled trends well")
        print()

    # Analyze potential improvement
    print("=" * 80)
    print("BREAKOUT MODULE IMPACT ESTIMATE")
    print("=" * 80)
    print()

    # Assume breakout module would:
    # - Trade the trending markets (ADX >= 25)
    # - Achieve 55-60% win rate (conservative estimate)
    # - Similar risk/reward to ranging trades

    if len(trending) > 0:
        current_trending_profit = trending['profit'].sum()
        current_trending_win_rate = (trending['win'].sum() / len(trending)) * 100

        # Estimate breakout performance
        avg_trade_size = abs(df['profit'].mean())
        estimated_breakout_win_rate = 57.5  # Conservative middle estimate
        estimated_trades = len(trending)
        estimated_wins = int(estimated_trades * estimated_breakout_win_rate / 100)
        estimated_avg_win = abs(ranging[ranging['win']]['profit'].mean()) if len(ranging[ranging['win']]) > 0 else avg_trade_size
        estimated_avg_loss = ranging[~ranging['win']]['profit'].mean() if len(ranging[~ranging['win']]) > 0 else -avg_trade_size

        estimated_profit = (estimated_wins * estimated_avg_win) + ((estimated_trades - estimated_wins) * estimated_avg_loss)

        print(f"Current Trending Market Results:")
        print(f"  Trades: {len(trending)}")
        print(f"  Win Rate: {current_trending_win_rate:.1f}%")
        print(f"  Total P/L: ${current_trending_profit:.2f}")
        print()

        print(f"Estimated Breakout Module Performance (conservative):")
        print(f"  Trades: {estimated_trades}")
        print(f"  Win Rate: {estimated_breakout_win_rate:.1f}% (assumed)")
        print(f"  Estimated P/L: ${estimated_profit:.2f}")
        print()

        improvement = estimated_profit - current_trending_profit
        improvement_pct = (improvement / abs(current_trending_profit)) * 100 if current_trending_profit != 0 else 0

        if improvement > 0:
            print(f"💰 POTENTIAL IMPROVEMENT: +${improvement:.2f} ({improvement_pct:+.1f}%)")
        else:
            print(f"⚠️  ESTIMATED CHANGE: ${improvement:.2f} ({improvement_pct:+.1f}%)")
        print()

    # Optimal ADX threshold analysis
    print("=" * 80)
    print("OPTIMAL ADX THRESHOLD ANALYSIS")
    print("=" * 80)
    print()

    print("Testing different ADX thresholds for strategy switching:")
    print()

    for threshold in [20, 23, 25, 27, 30]:
        ranging_thresh = df[df['adx'] < threshold]
        trending_thresh = df[df['adx'] >= threshold]

        ranging_wr = (ranging_thresh['win'].sum() / len(ranging_thresh)) * 100 if len(ranging_thresh) > 0 else 0
        trending_wr = (trending_thresh['win'].sum() / len(trending_thresh)) * 100 if len(trending_thresh) > 0 else 0

        ranging_profit = ranging_thresh['profit'].sum() if len(ranging_thresh) > 0 else 0
        trending_profit = trending_thresh['profit'].sum() if len(trending_thresh) > 0 else 0

        print(f"ADX Threshold: {threshold}")
        print(f"  Ranging (ADX < {threshold}): {len(ranging_thresh)} trades, {ranging_wr:.1f}% WR, ${ranging_profit:.2f} P/L")
        print(f"  Trending (ADX >= {threshold}): {len(trending_thresh)} trades, {trending_wr:.1f}% WR, ${trending_profit:.2f} P/L")
        print()

    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print()

    # Generate recommendations
    ranging_wr = (ranging['win'].sum() / len(ranging)) * 100 if len(ranging) > 0 else 0
    trending_wr = (trending['win'].sum() / len(trending)) * 100 if len(trending) > 0 else 0

    if ranging_wr > trending_wr + 5:
        print("✅ STRONG CASE for Breakout Module:")
        print(f"   Mean reversion performs {ranging_wr - trending_wr:.1f}% better in ranging markets")
        print(f"   {len(trending)} trending market trades ({len(trending)/len(df)*100:.1f}%) could benefit from breakout strategy")
        print()
        print("🎯 Next Steps:")
        print("   1. Build breakout detector for trending markets (ADX >= 25)")
        print("   2. Use strategy router to switch based on market condition")
        print("   3. Expected to improve overall performance by capturing trends")
    elif trending_wr > ranging_wr + 5:
        print("⚠️  UNEXPECTED: Mean reversion actually works better in trending markets")
        print("   This suggests the EA might already have trend-following characteristics")
        print("   Review entry logic to understand why")
    else:
        print("📊 NEUTRAL: Similar performance in both regimes")
        print("   Breakout module may still add value by:")
        print("   - Better optimized for trending conditions")
        print("   - More trade opportunities")
        print("   - Risk diversification")


if __name__ == "__main__":
    csv_path = "ea_reverse_engineering_detailed.csv"

    if not Path(csv_path).exists():
        print(f"❌ Error: {csv_path} not found")
        print(f"   Looking in: {Path.cwd()}")
        exit(1)

    analyze_by_adx_regime(csv_path)
