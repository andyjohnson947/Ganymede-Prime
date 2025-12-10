#!/usr/bin/env python3
"""
Real-Time Signal Status Checker
Shows exactly why signals are or aren't being generated RIGHT NOW
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'trading_bot'))

try:
    import MetaTrader5 as mt5
    import pandas as pd
    import numpy as np
    from datetime import datetime

    print("=" * 80)
    print("REAL-TIME SIGNAL STATUS CHECKER")
    print("=" * 80)

    # Check if MT5 is available
    print("\n🔌 Checking MT5 connection...")

    if not mt5.initialize():
        print("❌ MT5 not initialized")
        print("\nPossible reasons:")
        print("  1. MT5 terminal not running")
        print("  2. MT5 not installed")
        print("  3. Need to login first")
        print("\nTo connect:")
        print("  1. Open MT5 terminal")
        print("  2. Login to your account")
        print("  3. Run this script again")
        sys.exit(1)

    account_info = mt5.account_info()
    if account_info:
        print(f"✅ Connected to MT5 account: {account_info.login}")
        print(f"   Balance: ${account_info.balance:.2f}")
        print(f"   Equity: ${account_info.equity:.2f}")
    else:
        print("⚠️  MT5 initialized but no account connected")

    # Check EURUSD data
    print("\n📊 Checking EURUSD market data...")

    symbol = "EURUSD"
    timeframe = mt5.TIMEFRAME_H1

    # Get recent bars
    bars = mt5.copy_rates_from_pos(symbol, timeframe, 0, 200)

    if bars is None or len(bars) == 0:
        print(f"❌ Cannot get {symbol} data")
        print("\nPossible reasons:")
        print(f"  1. {symbol} not in Market Watch")
        print("  2. Symbol name different (EURUSD vs EURUSDm)")
        print("  3. No historical data loaded")
        print("\nTo fix:")
        print(f"  1. Open MT5 → Market Watch")
        print(f"  2. Right-click → Add {symbol}")
        print("  3. Open an H1 chart to load history")
        mt5.shutdown()
        sys.exit(1)

    df = pd.DataFrame(bars)
    df['time'] = pd.to_datetime(df['time'], unit='s')

    latest = df.iloc[-1]
    current_price = latest['close']

    print(f"✅ Received {len(df)} H1 bars")
    print(f"   Current price: {current_price:.5f}")
    print(f"   Latest bar: {latest['time']}")

    # Calculate VWAP
    print("\n📈 Calculating VWAP and bands...")

    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
    df['vwap'] = (df['typical_price'] * df['tick_volume']).cumsum() / df['tick_volume'].cumsum()

    # Calculate standard deviation
    df['vwap_diff'] = df['typical_price'] - df['vwap']
    df['vwap_diff_sq'] = df['vwap_diff'] ** 2
    df['vwap_variance'] = (df['vwap_diff_sq'] * df['tick_volume']).cumsum() / df['tick_volume'].cumsum()
    df['vwap_std'] = np.sqrt(df['vwap_variance'])

    # VWAP bands
    df['vwap_upper_1'] = df['vwap'] + df['vwap_std']
    df['vwap_lower_1'] = df['vwap'] - df['vwap_std']
    df['vwap_upper_2'] = df['vwap'] + (df['vwap_std'] * 2)
    df['vwap_lower_2'] = df['vwap'] - (df['vwap_std'] * 2)

    latest_vwap = df.iloc[-1]
    vwap = latest_vwap['vwap']
    std = latest_vwap['vwap_std']

    print(f"   VWAP: {vwap:.5f}")
    print(f"   Std Dev: {std:.5f}")
    print(f"   Band +1σ: {latest_vwap['vwap_upper_1']:.5f}")
    print(f"   Band -1σ: {latest_vwap['vwap_lower_1']:.5f}")
    print(f"   Band +2σ: {latest_vwap['vwap_upper_2']:.5f}")
    print(f"   Band -2σ: {latest_vwap['vwap_lower_2']:.5f}")

    # Check VWAP position
    print("\n🎯 VWAP Position Check:")

    distance_from_vwap = ((current_price - vwap) / vwap) * 100

    if current_price > latest_vwap['vwap_upper_2']:
        vwap_status = "ABOVE Band 2 (2σ) - SELL SIGNAL ZONE ✅"
        in_band = True
    elif current_price > latest_vwap['vwap_upper_1']:
        vwap_status = "ABOVE Band 1 (1σ) - SELL SIGNAL ZONE ✅"
        in_band = True
    elif current_price < latest_vwap['vwap_lower_2']:
        vwap_status = "BELOW Band 2 (2σ) - BUY SIGNAL ZONE ✅"
        in_band = True
    elif current_price < latest_vwap['vwap_lower_1']:
        vwap_status = "BELOW Band 1 (1σ) - BUY SIGNAL ZONE ✅"
        in_band = True
    else:
        vwap_status = "NEAR VWAP CENTER - NO SIGNAL ❌"
        in_band = False

    print(f"   Price vs VWAP: {distance_from_vwap:+.3f}%")
    print(f"   Status: {vwap_status}")

    # Calculate ADX
    print("\n📊 Calculating ADX (Trend Filter)...")

    # Simple ADX calculation
    period = 14
    df['high_diff'] = df['high'].diff()
    df['low_diff'] = -df['low'].diff()

    df['plus_dm'] = np.where((df['high_diff'] > df['low_diff']) & (df['high_diff'] > 0), df['high_diff'], 0)
    df['minus_dm'] = np.where((df['low_diff'] > df['high_diff']) & (df['low_diff'] > 0), df['low_diff'], 0)

    df['tr'] = df[['high', 'low', 'close']].apply(
        lambda x: max(x['high'] - x['low'],
                     abs(x['high'] - df['close'].shift(1).iloc[x.name]),
                     abs(x['low'] - df['close'].shift(1).iloc[x.name]) if x.name > 0 else 0),
        axis=1
    )

    df['atr'] = df['tr'].rolling(period).mean()
    df['plus_di'] = 100 * (df['plus_dm'].rolling(period).mean() / df['atr'])
    df['minus_di'] = 100 * (df['minus_dm'].rolling(period).mean() / df['atr'])

    df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
    df['adx'] = df['dx'].rolling(period).mean()

    latest_adx = df.iloc[-1]
    adx_value = latest_adx['adx']
    plus_di = latest_adx['plus_di']
    minus_di = latest_adx['minus_di']

    print(f"   ADX: {adx_value:.2f}")
    print(f"   +DI: {plus_di:.2f}")
    print(f"   -DI: {minus_di:.2f}")

    # Check trend filter
    print("\n🚦 Trend Filter Check:")

    if adx_value > 40:
        trend_status = f"STRONG TREND (ADX {adx_value:.1f} > 40) - BLOCKED ❌"
        trend_pass = False
    elif adx_value > 25:
        trend_status = f"TRENDING (ADX {adx_value:.1f} > 25) - BLOCKED ❌"
        trend_pass = False
    elif adx_value > 20:
        trend_status = f"WEAK TREND (ADX {adx_value:.1f}, 20-25) - ALLOWED ⚠️"
        trend_pass = True
    else:
        trend_status = f"RANGING (ADX {adx_value:.1f} < 20) - ALLOWED ✅"
        trend_pass = True

    print(f"   {trend_status}")

    # Final verdict
    print("\n" + "=" * 80)
    print("🎯 SIGNAL STATUS SUMMARY")
    print("=" * 80)

    if in_band and trend_pass:
        print("\n✅ SIGNAL CONDITIONS MET!")
        print(f"   • VWAP: {vwap_status}")
        print(f"   • Trend: {trend_status}")
        print("\n   ⚠️  Note: Still need confluence score ≥ 4")
        print("   (VWAP band alone = 1 point, need 3 more from HTF levels)")
    elif in_band and not trend_pass:
        print("\n❌ NO SIGNAL - BLOCKED BY TREND FILTER")
        print(f"   • VWAP: {vwap_status}")
        print(f"   • Trend: {trend_status}")
        print(f"\n   💡 Market is trending (ADX {adx_value:.1f})")
        print("   Your EA is designed for ranging markets only")
        print("   This is CORRECT behavior - protects you from trends")
    elif not in_band and trend_pass:
        print("\n❌ NO SIGNAL - PRICE NOT AT VWAP BAND")
        print(f"   • VWAP: {vwap_status}")
        print(f"   • Trend: {trend_status}")
        print(f"\n   💡 Price is {distance_from_vwap:+.3f}% from VWAP")
        print("   Need price to reach ±1σ or ±2σ band")
        print(f"   Wait for price to reach: {latest_vwap['vwap_lower_1']:.5f} or {latest_vwap['vwap_upper_1']:.5f}")
    else:
        print("\n❌ NO SIGNAL - MULTIPLE BLOCKS")
        print(f"   • VWAP: {vwap_status}")
        print(f"   • Trend: {trend_status}")

    print("\n" + "=" * 80)
    print("💡 RECOMMENDATIONS")
    print("=" * 80)

    if not trend_pass:
        print("\n**Market is trending - this is NORMAL**")
        print("• Your EA averaged 82.4% success in RANGING markets")
        print("• Trend filter prevents losses in trending markets")
        print("• Wait for ADX to drop below 25")
        print("• Check back in a few hours")

    if not in_band:
        print("\n**Price not at VWAP band - this is NORMAL**")
        print("• Signals only trigger at specific price levels")
        print("• May take hours for setup to form")
        print("• Monitor for price to reach bands")

    if in_band and trend_pass:
        print("\n**Conditions look good!**")
        print("• Make sure bot is actually running")
        print("• Check logs/signals.log for confluence score")
        print("• May need higher timeframe confluence (prev day levels, etc.)")

    print("\n" + "=" * 80)

    mt5.shutdown()

except ImportError:
    print("=" * 80)
    print("REAL-TIME SIGNAL STATUS CHECKER")
    print("=" * 80)
    print("\n❌ MetaTrader5 library not installed")
    print("\nTo install:")
    print("  pip install MetaTrader5")
    print("\nOr run:")
    print("  pip install -r requirements.txt")
    sys.exit(1)

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    if 'mt5' in dir():
        mt5.shutdown()
    sys.exit(1)
