#!/usr/bin/env python3
"""
ADX Diagnostic Tool
Shows what's happening with ADX calculation and why values might be high
"""

import MetaTrader5 as mt5
import pandas as pd
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, '.')

from trading_bot.indicators.adx import calculate_adx, interpret_adx


def diagnose_adx(login: int, password: str, server: str, symbol: str = 'EURUSD'):
    """
    Diagnose ADX calculation and show intermediate values

    Args:
        login: MT5 account
        password: Password
        server: Server name
        symbol: Symbol to analyze
    """

    print("=" * 80)
    print("ADX DIAGNOSTIC TOOL")
    print("=" * 80)
    print()

    # Initialize MT5
    if not mt5.initialize():
        print("❌ Failed to initialize MT5")
        return

    # Login
    if not mt5.login(login, password=password, server=server):
        print("❌ Login failed")
        mt5.shutdown()
        return

    print(f"✅ Connected to {server}")
    print()

    # Get symbol info
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"❌ Symbol {symbol} not found")
        # Try alternative formats
        for alt in [f"{symbol}.a", f"{symbol}m", f"{symbol}-sb"]:
            if mt5.symbol_info(alt):
                symbol = alt
                print(f"✅ Found alternative: {symbol}")
                break
        else:
            mt5.shutdown()
            return

    print(f"📊 Symbol: {symbol}")
    print(f"   Current Bid: {symbol_info.bid}")
    print(f"   Current Ask: {symbol_info.ask}")
    print()

    # Get historical data (need enough for ADX calculation)
    # ADX needs 2-3x the period for accurate calculation
    lookback = 100  # Get 100 bars

    print(f"📈 Fetching {lookback} H1 bars for ADX calculation...")
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, lookback)

    if rates is None or len(rates) == 0:
        print("❌ Failed to get historical data")
        mt5.shutdown()
        return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')

    print(f"✅ Got {len(df)} bars")
    print(f"   From: {df['time'].iloc[0]}")
    print(f"   To: {df['time'].iloc[-1]}")
    print()

    # Calculate ADX
    print("🔢 Calculating ADX (period=14)...")
    df_with_adx = calculate_adx(df, period=14)

    # Get latest values
    latest = df_with_adx.iloc[-1]
    adx_value = latest['adx']
    plus_di = latest['plus_di']
    minus_di = latest['minus_di']

    print(f"✅ ADX calculated")
    print()

    # Show current ADX
    print("=" * 80)
    print("CURRENT ADX VALUES")
    print("=" * 80)
    print()

    print(f"ADX: {adx_value:.2f}")
    print(f"+DI: {plus_di:.2f}")
    print(f"-DI: {minus_di:.2f}")
    print()

    # Interpret ADX
    interpretation = interpret_adx(adx_value, plus_di, minus_di)

    print(f"Market Type: {interpretation['market_type'].upper()}")
    print(f"Trend Strength: {interpretation['strength'].upper()}")
    print(f"Direction: {interpretation['direction'].upper()}")
    print(f"Confidence: {interpretation['confidence']:.2f}")
    print()

    if adx_value < 20:
        print("✅ RANGING MARKET - Good for mean reversion")
    elif adx_value < 25:
        print("⚠️  WEAK TREND - Borderline for mean reversion")
    elif adx_value < 40:
        print("❌ TRENDING MARKET - Mean reversion risky")
    else:
        print("🚫 STRONG TREND - Mean reversion UNSAFE (blocked)")
    print()

    # Show ADX over time
    print("=" * 80)
    print("ADX HISTORY (Last 20 bars)")
    print("=" * 80)
    print()

    recent_20 = df_with_adx.tail(20)

    print(f"{'Time':<20} {'ADX':>6} {'+DI':>6} {'-DI':>6} {'Status':<15}")
    print("-" * 80)

    for idx, row in recent_20.iterrows():
        time_str = row['time'].strftime('%Y-%m-%d %H:%M')
        adx = row['adx']
        pdi = row['plus_di']
        mdi = row['minus_di']

        if adx < 20:
            status = "RANGING"
        elif adx < 25:
            status = "WEAK TREND"
        elif adx < 40:
            status = "TRENDING"
        else:
            status = "STRONG TREND"

        print(f"{time_str:<20} {adx:>6.2f} {pdi:>6.2f} {mdi:>6.2f} {status:<15}")

    print()

    # Check if ADX is stable
    print("=" * 80)
    print("ADX STABILITY CHECK")
    print("=" * 80)
    print()

    last_10_adx = df_with_adx.tail(10)['adx'].values
    adx_mean = last_10_adx.mean()
    adx_std = last_10_adx.std()
    adx_min = last_10_adx.min()
    adx_max = last_10_adx.max()
    adx_range = adx_max - adx_min

    print(f"Last 10 bars:")
    print(f"  Mean ADX: {adx_mean:.2f}")
    print(f"  Std Dev: {adx_std:.2f}")
    print(f"  Range: {adx_min:.2f} - {adx_max:.2f} (spread: {adx_range:.2f})")
    print()

    if adx_std < 5:
        print("✅ ADX is STABLE (low volatility)")
    elif adx_std < 10:
        print("⚠️  ADX is MODERATELY STABLE")
    else:
        print("❌ ADX is UNSTABLE (high volatility)")
    print()

    # Check if market is actually trending
    print("=" * 80)
    print("PRICE ACTION ANALYSIS")
    print("=" * 80)
    print()

    last_20_prices = df_with_adx.tail(20)

    # Calculate price movement
    first_close = last_20_prices.iloc[0]['close']
    last_close = last_20_prices.iloc[-1]['close']
    price_change = last_close - first_close
    price_change_pct = (price_change / first_close) * 100
    price_high = last_20_prices['high'].max()
    price_low = last_20_prices['low'].min()
    price_range = price_high - price_low
    price_range_pct = (price_range / first_close) * 100

    print(f"Last 20 bars:")
    print(f"  Price change: {price_change_pct:+.2f}%")
    print(f"  Price range: {price_range_pct:.2f}%")
    print(f"  From: {first_close:.5f}")
    print(f"  To: {last_close:.5f}")
    print()

    # Count consecutive candles
    closes = last_20_prices['close'].values
    opens = last_20_prices['open'].values
    bullish = (closes > opens).sum()
    bearish = (closes < opens).sum()

    print(f"Candle direction:")
    print(f"  Bullish: {bullish}/{len(last_20_prices)} ({bullish/len(last_20_prices)*100:.1f}%)")
    print(f"  Bearish: {bearish}/{len(last_20_prices)} ({bearish/len(last_20_prices)*100:.1f}%)")
    print()

    # Recommendation
    print("=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    print()

    if adx_value > 40:
        print(f"🚫 ADX = {adx_value:.1f} is TOO HIGH for mean reversion")
        print()
        print("   The market is in a STRONG TREND.")
        print("   Mean reversion strategy will be blocked (correct behavior).")
        print()
        if price_change_pct > 0.5:
            print("   ↗️  Strong UPTREND detected")
        elif price_change_pct < -0.5:
            print("   ↘️  Strong DOWNTREND detected")
        print()
        print("   Wait for:")
        print("   - ADX to decline below 25 (ranging market returns)")
        print("   - Or consider breakout strategy (shelved for now)")
    elif adx_value > 25:
        print(f"⚠️  ADX = {adx_value:.1f} indicates TRENDING market")
        print()
        print("   Mean reversion may work but is risky.")
        print("   Wait for ADX < 25 for safer mean reversion opportunities.")
    else:
        print(f"✅ ADX = {adx_value:.1f} is GOOD for mean reversion")
        print()
        print("   Market is ranging - ideal conditions for your strategy.")

    mt5.shutdown()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python diagnose_adx.py <login> <password> <server> [symbol]")
        print()
        print("Example:")
        print("  python diagnose_adx.py 12345 yourpass 'StarTrader-Demo' EURUSD")
        sys.exit(1)

    login = int(sys.argv[1])
    password = sys.argv[2]
    server = sys.argv[3]
    symbol = sys.argv[4] if len(sys.argv) > 4 else 'EURUSD'

    diagnose_adx(login, password, server, symbol)
