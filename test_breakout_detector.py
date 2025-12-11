#!/usr/bin/env python3
"""
Standalone Test for Breakout Detector
Tests LVN breakout detection with live MT5 data WITHOUT integration

Usage:
    python test_breakout_detector.py <login> <password> <server> [symbol]

Example:
    python test_breakout_detector.py 12345 yourpass "VantageInternational-Demo" EURUSD
"""

import MetaTrader5 as mt5
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime

# Add paths
sys.path.insert(0, str(Path(__file__).parent))

from breakout_strategy.strategies.breakout_detector import BreakoutDetector
from breakout_strategy.indicators.volume_analyzer import VolumeAnalyzer, format_volume_summary
from trading_bot.indicators.vwap import VWAP
from trading_bot.indicators.volume_profile import VolumeProfile


def test_breakout_detector(login: int, password: str, server: str, symbol: str = 'EURUSD'):
    """
    Test breakout detector with live market data

    Args:
        login: MT5 account
        password: Password
        server: Server name
        symbol: Symbol to test
    """

    print("=" * 80)
    print("BREAKOUT DETECTOR - STANDALONE TEST")
    print("=" * 80)
    print()

    # Initialize MT5
    if not mt5.initialize():
        print("❌ Failed to initialize MT5")
        return

    # Login
    if not mt5.login(login, password=password, server=server):
        print("❌ Login failed")
        error = mt5.last_error()
        print(f"   Error: {error}")
        mt5.shutdown()
        return

    print(f"✅ Connected to {server}")
    print()

    # Get symbol info
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"❌ Symbol {symbol} not found")
        # Try alternatives
        for alt in [f"{symbol}.a", f"{symbol}m", f"{symbol}-sb"]:
            if mt5.symbol_info(alt):
                symbol = alt
                symbol_info = mt5.symbol_info(symbol)
                print(f"✅ Found alternative: {symbol}")
                break
        else:
            mt5.shutdown()
            return

    print(f"📊 Testing Symbol: {symbol}")
    print(f"   Bid: {symbol_info.bid:.5f}")
    print(f"   Ask: {symbol_info.ask:.5f}")
    print()

    # Fetch data
    print("📈 Fetching market data...")

    # H1 data (primary timeframe)
    h1_bars = 200
    h1_data = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, h1_bars)

    # Daily data (HTF context)
    daily_bars = 50
    daily_data = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, daily_bars)

    # Weekly data (HTF context)
    weekly_bars = 20
    weekly_data = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_W1, 0, weekly_bars)

    if h1_data is None or daily_data is None or weekly_data is None:
        print("❌ Failed to fetch market data")
        mt5.shutdown()
        return

    # Convert to DataFrames
    h1_df = pd.DataFrame(h1_data)
    daily_df = pd.DataFrame(daily_data)
    weekly_df = pd.DataFrame(weekly_data)

    # Add time column
    h1_df['time'] = pd.to_datetime(h1_df['time'], unit='s')
    daily_df['time'] = pd.to_datetime(daily_df['time'], unit='s')
    weekly_df['time'] = pd.to_datetime(weekly_df['time'], unit='s')

    print(f"✅ Fetched data:")
    print(f"   H1: {len(h1_df)} bars (from {h1_df['time'].iloc[0]} to {h1_df['time'].iloc[-1]})")
    print(f"   Daily: {len(daily_df)} bars")
    print(f"   Weekly: {len(weekly_df)} bars")
    print()

    # Calculate indicators
    print("🔧 Calculating indicators...")

    # VWAP
    vwap_calculator = VWAP()
    h1_df = vwap_calculator.calculate(h1_df)

    # Volume Profile
    vp_calculator = VolumeProfile()
    h1_df = vp_calculator.calculate(h1_df)

    print("✅ Indicators calculated")
    print()

    # Test volume analyzer
    print("=" * 80)
    print("VOLUME ANALYSIS")
    print("=" * 80)
    print()

    volume_analyzer = VolumeAnalyzer(lookback=20)
    volume_summary = volume_analyzer.get_volume_summary(h1_df)

    print(format_volume_summary(volume_summary))
    print()
    print(f"Current Volume: {volume_summary['current_volume']:.0f}")
    print(f"Average Volume: {volume_summary['average_volume']:.0f}")
    print(f"Volume Ratio: {volume_summary['volume_ratio']:.2f}x")
    print(f"Percentile: {volume_summary['percentile']:.1f}th")
    print(f"Trend: {volume_summary['volume_trend']}")
    print(f"Breakout Validation: {volume_summary['breakout_validation']['recommendation']} ({volume_summary['breakout_validation']['quality']})")
    print()

    # Test breakout detector
    print("=" * 80)
    print("BREAKOUT DETECTION")
    print("=" * 80)
    print()

    detector = BreakoutDetector()

    print("🔍 Scanning for breakout signals...")
    print()

    signal = detector.detect_breakout(
        current_data=h1_df,
        daily_data=daily_df,
        weekly_data=weekly_df,
        symbol=symbol
    )

    if signal:
        print("🚀 BREAKOUT SIGNAL DETECTED!")
        print()
        print(detector.get_breakout_summary(signal))
        print()

        print("Signal Details:")
        print(f"  Symbol: {signal['symbol']}")
        print(f"  Direction: {signal['direction'].upper()}")
        print(f"  Entry Type: {signal['entry_type']}")
        print(f"  Entry Price: {signal['entry_price']:.5f}")
        print(f"  Stop Loss: {signal['stop_loss']:.5f}")
        print(f"  Take Profit: {signal['take_profit']:.5f}")
        print(f"  Confluence Score: {signal['confluence_score']}")
        print(f"  Factors: {', '.join(signal['factors'])}")
        print()

        # Calculate R:R
        if signal['stop_loss'] and signal['take_profit']:
            risk = abs(signal['entry_price'] - signal['stop_loss'])
            reward = abs(signal['take_profit'] - signal['entry_price'])
            rr_ratio = reward / risk if risk > 0 else 0
            print(f"  Risk/Reward: 1:{rr_ratio:.2f}")
            print()

    else:
        print("⏸️  No breakout signal detected")
        print()

        # Show why
        latest = h1_df.iloc[-1]
        print("Current Market Conditions:")

        if 'adx' in h1_df.columns:
            adx = latest['adx']
            print(f"  ADX: {adx:.1f}", end="")
            if adx < 25:
                print(" ❌ (Ranging market - need ADX >= 25)")
            elif adx >= 40:
                print(" ⚠️  (Very strong trend - conservative entry only)")
            else:
                print(" ✅ (Trending market)")

        if 'vwap' in h1_df.columns:
            price = latest['close']
            vwap = latest['vwap']
            vwap_dist_pct = abs(price - vwap) / vwap * 100
            print(f"  VWAP Distance: {vwap_dist_pct:.2f}%", end="")
            if vwap_dist_pct < 0.1:
                print(" ❌ (Too close to VWAP - no clear bias)")
            else:
                print(f" ✅ ({'Above' if price > vwap else 'Below'} VWAP)")

        if 'lvn_percentile' in h1_df.columns and not pd.isna(latest['lvn_percentile']):
            lvn_pct = latest['lvn_percentile']
            print(f"  LVN Percentile: {lvn_pct:.0f}th", end="")
            if lvn_pct < 30:
                print(" ✅ (At low volume area)")
            else:
                print(" ❌ (Not at LVN)")

        print(f"  Volume Percentile: {volume_summary['percentile']:.0f}th", end="")
        if volume_summary['percentile'] >= 70:
            print(" ✅ (High volume)")
        elif volume_summary['percentile'] >= 50:
            print(" ⚠️  (Average volume)")
        else:
            print(" ❌ (Low volume)")

        print()
        print("💡 Waiting for:")
        print("   - Market to trend (ADX >= 25)")
        print("   - Price at LVN (low volume node)")
        print("   - Clear VWAP directional bias")
        print("   - Volume expansion confirmation")
        print("   - Minimum confluence score: 6")
        print()

    # Show recent tracked breakouts (for retest detection)
    if detector.recent_breakouts:
        print("=" * 80)
        print("TRACKED BREAKOUT LEVELS (Waiting for Retest)")
        print("=" * 80)
        print()

        for sym, breakout in detector.recent_breakouts.items():
            print(f"  {sym}: {breakout['level']:.5f} ({breakout['direction'].upper()}) - Tracked at {breakout['time']}")
        print()

    mt5.shutdown()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python test_breakout_detector.py <login> <password> <server> [symbol]")
        print()
        print("Example:")
        print("  python test_breakout_detector.py 12345 yourpass 'VantageInternational-Demo' EURUSD")
        sys.exit(1)

    login = int(sys.argv[1])
    password = sys.argv[2]
    server = sys.argv[3]
    symbol = sys.argv[4] if len(sys.argv) > 4 else 'EURUSD'

    test_breakout_detector(login, password, server, symbol)
