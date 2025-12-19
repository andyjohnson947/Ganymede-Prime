#!/usr/bin/env python3
"""
Trade Debug Tool - Find out why bot isn't opening trades

Checks:
1. Trading suspension status
2. Current regime detection (M30)
3. Confluence signals present
4. Risk limits
5. Data fetching
6. Signal detection step-by-step

Usage:
    python debug_no_trades.py --login 12345 --password "pass" --server "Broker"
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent / 'trading_bot'))

from core.mt5_manager import MT5Manager
from strategies.signal_detector import SignalDetector
from indicators.advanced_regime_detector import AdvancedRegimeDetector
from utils.risk_calculator import RiskCalculator
from config.strategy_config import (
    SYMBOLS, TIMEFRAME, HTF_TIMEFRAMES, MIN_CONFLUENCE_SCORE,
    MAX_OPEN_POSITIONS, MAX_POSITIONS_PER_SYMBOL
)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Debug why bot is not opening trades')

    parser.add_argument('--login', type=int, required=True, help='MT5 account login')
    parser.add_argument('--password', type=str, required=True, help='MT5 account password')
    parser.add_argument('--server', type=str, required=True, help='MT5 server name')

    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()

    print("=" * 80)
    print("🔍 TRADE DEBUG TOOL - Finding Why No Trades")
    print("=" * 80)
    print()

    # Connect to MT5
    print("🔌 Connecting to MT5...")
    mt5 = MT5Manager(login=args.login, password=args.password, server=args.server)

    if not mt5.connect():
        print("❌ Failed to connect to MT5")
        sys.exit(1)

    print("✅ MT5 Connected\n")

    # Get account info
    account_info = mt5.get_account_info()
    print(f"💰 Account Info:")
    print(f"   Balance: ${account_info['balance']:.2f}")
    print(f"   Equity: ${account_info['equity']:.2f}")
    print(f"   Margin Free: ${account_info.get('margin_free', 0):.2f}\n")

    # Check current positions
    positions = mt5.get_positions()
    print(f"📊 Current Positions: {len(positions) if positions else 0}")
    if positions:
        for pos in positions:
            pos_type = 'BUY' if pos['type'] == 0 else 'SELL'
            print(f"   #{pos['ticket']} {pos['symbol']} {pos_type} {pos['volume']} @ {pos['price_open']:.5f} | P&L: ${pos['profit']:.2f}")
    print()

    # Check position limits
    print(f"⚙️  Risk Limits:")
    print(f"   MAX_OPEN_POSITIONS: {MAX_OPEN_POSITIONS}")
    print(f"   MAX_POSITIONS_PER_SYMBOL: {MAX_POSITIONS_PER_SYMBOL}")
    print(f"   Current total positions: {len(positions) if positions else 0}")

    # Count per symbol
    symbol_counts = {}
    if positions:
        for pos in positions:
            symbol = pos['symbol']
            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1

    for symbol in SYMBOLS:
        count = symbol_counts.get(symbol, 0)
        status = "✅ ALLOWED" if count < MAX_POSITIONS_PER_SYMBOL else "❌ BLOCKED"
        print(f"   {symbol}: {count}/{MAX_POSITIONS_PER_SYMBOL} positions - {status}")

    print()

    # Initialize components
    signal_detector = SignalDetector()
    regime_detector = AdvancedRegimeDetector()
    risk_calculator = RiskCalculator()

    # Check each symbol
    for symbol in SYMBOLS:
        print("=" * 80)
        print(f"🔍 DEBUGGING {symbol}")
        print("=" * 80)
        print()

        # 1. Fetch data
        print(f"📥 Fetching data...")
        h1_data = mt5.get_historical_data(symbol, 'H1', bars=500)
        m30_data = mt5.get_historical_data(symbol, 'M30', bars=200)
        d1_data = mt5.get_historical_data(symbol, 'D1', bars=100)
        w1_data = mt5.get_historical_data(symbol, 'W1', bars=50)

        if h1_data is None:
            print(f"   ❌ Failed to fetch H1 data\n")
            continue
        if m30_data is None:
            print(f"   ❌ Failed to fetch M30 data\n")
            continue
        if d1_data is None or w1_data is None:
            print(f"   ❌ Failed to fetch D1/W1 data\n")
            continue

        print(f"   ✅ H1: {len(h1_data)} bars")
        print(f"   ✅ M30: {len(m30_data)} bars")
        print(f"   ✅ D1: {len(d1_data)} bars")
        print(f"   ✅ W1: {len(w1_data)} bars\n")

        # 2. Check M30 regime
        print(f"🌍 M30 Regime Detection:")
        regime_info = regime_detector.detect_regime(m30_data)
        is_safe, reason = regime_detector.is_safe_for_recovery(m30_data, min_confidence=0.60)

        print(f"   Regime: {regime_info['regime'].upper()}")
        print(f"   Hurst: {regime_info['hurst']:.3f} ({'< 0.45 = ranging' if regime_info['hurst'] < 0.45 else '> 0.55 = trending' if regime_info['hurst'] > 0.55 else 'transitional'})")
        print(f"   VHF: {regime_info['vhf']:.3f} ({'< 0.25 = ranging' if regime_info['vhf'] < 0.25 else '> 0.40 = trending' if regime_info['vhf'] > 0.40 else 'transitional'})")
        print(f"   VHF Trend: {regime_info.get('vhf_trend', 'UNKNOWN')}")
        print(f"   Confidence: {regime_info['confidence']:.0%}")
        print(f"   Recovery Safe: {'✅ YES' if is_safe else '❌ NO'}")
        print(f"   Reason: {reason}\n")

        if not is_safe:
            print(f"   ⚠️  WARNING: M30 regime blocking trades/recovery!")
            print(f"   This might be why no trades are opening.\n")

        # 3. Calculate VWAP for signal detection
        print(f"📊 Checking for Signals...")
        h1_data_vwap = signal_detector.vwap.calculate(h1_data)

        # 4. Detect signal
        signal = signal_detector.detect_signal(
            current_data=h1_data_vwap,
            daily_data=d1_data,
            weekly_data=w1_data,
            symbol=symbol
        )

        if signal is None:
            print(f"   ❌ NO SIGNAL DETECTED\n")

            # Show why
            latest = h1_data_vwap.iloc[-1]
            current_price = latest['close']

            print(f"   Current Price: {current_price:.5f}")

            if 'vwap' in latest.index:
                vwap = latest['vwap']
                distance_pct = abs(current_price - vwap) / vwap * 100
                print(f"   VWAP: {vwap:.5f} (distance: {distance_pct:.2f}%)")

            if 'upper_band_1' in latest.index:
                print(f"   VWAP Band 1: {latest['lower_band_1']:.5f} - {latest['upper_band_1']:.5f}")
            if 'upper_band_2' in latest.index:
                print(f"   VWAP Band 2: {latest['lower_band_2']:.5f} - {latest['upper_band_2']:.5f}")

            print(f"\n   💡 Price needs to be AT VWAP bands for signal")
            print(f"   💡 Or at POC/LVN/VAH/VAL levels")
            print(f"   💡 With minimum confluence score of {MIN_CONFLUENCE_SCORE}\n")

        else:
            print(f"   ✅ SIGNAL DETECTED!")
            print(f"   Direction: {signal['direction'].upper()}")
            print(f"   Price: {signal['price']:.5f}")
            print(f"   Confluence Score: {signal['confluence_score']}/{MIN_CONFLUENCE_SCORE}")
            print(f"   Factors: {', '.join(signal['factors'])}")
            print(f"   Strategy Mode: {signal.get('strategy_mode', 'mean_reversion')}")
            print(f"   Should Trade: {'✅ YES' if signal.get('should_trade') else '❌ NO (insufficient confluence)'}\n")

            if signal.get('should_trade'):
                # 5. Check risk validation
                print(f"🎲 Risk Validation:")
                symbol_info = mt5.get_symbol_info(symbol)
                volume = risk_calculator.calculate_position_size(
                    account_balance=account_info['balance'],
                    symbol_info=symbol_info
                )

                can_trade, risk_reason = risk_calculator.validate_trade(
                    account_info=account_info,
                    symbol_info=symbol_info,
                    volume=volume,
                    current_positions=positions,
                    mt5_manager=mt5
                )

                print(f"   Can Trade: {'✅ YES' if can_trade else '❌ NO'}")
                if not can_trade:
                    print(f"   Reason: {risk_reason}")
                    print(f"\n   ⚠️  THIS IS WHY TRADE NOT OPENING!")
                else:
                    print(f"   Position Size: {volume} lots")
                    print(f"\n   ✅ ALL CHECKS PASSED - TRADE SHOULD OPEN!")
                    print(f"\n   🤔 If bot is running and not trading, check:")
                    print(f"   - Is trading suspended? (check bot console)")
                    print(f"   - Is data refresh interval too long?")
                    print(f"   - Is bot actually running the check loop?")

        print()

    # Final summary
    print("=" * 80)
    print("📋 SUMMARY - Possible Reasons for No Trades")
    print("=" * 80)
    print()

    issues = []

    # Check regime blocking
    for symbol in SYMBOLS:
        m30_data = mt5.get_historical_data(symbol, 'M30', bars=200)
        if m30_data is not None:
            is_safe, _ = regime_detector.is_safe_for_recovery(m30_data)
            if not is_safe:
                issues.append(f"❌ {symbol}: M30 regime showing TRENDING (blocks trades)")

    # Check position limits
    if positions and len(positions) >= MAX_OPEN_POSITIONS:
        issues.append(f"❌ Max open positions reached ({len(positions)}/{MAX_OPEN_POSITIONS})")

    for symbol in SYMBOLS:
        count = symbol_counts.get(symbol, 0)
        if count >= MAX_POSITIONS_PER_SYMBOL:
            issues.append(f"❌ {symbol}: Max positions per symbol ({count}/{MAX_POSITIONS_PER_SYMBOL})")

    # Check if any signals present
    signals_found = False
    for symbol in SYMBOLS:
        h1_data = mt5.get_historical_data(symbol, 'H1', bars=500)
        d1_data = mt5.get_historical_data(symbol, 'D1', bars=100)
        w1_data = mt5.get_historical_data(symbol, 'W1', bars=50)

        if h1_data is not None and d1_data is not None and w1_data is not None:
            h1_data_vwap = signal_detector.vwap.calculate(h1_data)
            signal = signal_detector.detect_signal(h1_data_vwap, d1_data, w1_data, symbol)
            if signal and signal.get('should_trade'):
                signals_found = True

    if not signals_found:
        issues.append(f"❌ No valid confluence signals present (price not at VWAP setups)")

    if not issues:
        print("✅ No obvious issues found!")
        print("\nPossible reasons:")
        print("1. Bot not running?")
        print("2. Trading suspended from previous session?")
        print("3. Data refresh interval too long - signals being missed?")
        print("4. Check bot console for 'Trading suspended' messages")
    else:
        print("Found these issues:\n")
        for issue in issues:
            print(f"   {issue}")

    print()

    mt5.disconnect()


if __name__ == "__main__":
    main()
