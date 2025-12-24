#!/usr/bin/env python3
"""
Signal Diagnostic Tool - Analyze why signals aren't being detected
Scans the last 2 days of market data and shows what the bot is "seeing"
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'trading_bot'))

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
from trading_bot.strategies.signal_detector import SignalDetector
from trading_bot.strategies.time_filters import TimeFilter
from trading_bot.strategies.breakout_strategy import BreakoutStrategy
from trading_bot.portfolio.portfolio_manager import PortfolioManager
from trading_bot.config.strategy_config import (
    MIN_CONFLUENCE_SCORE,
    MEAN_REVERSION_HOURS,
    BREAKOUT_HOURS,
    BROKER_GMT_OFFSET,
)
from trading_bot.utils.timezone_manager import get_current_time


def get_mt5_data(symbol: str, timeframe, bars: int):
    """Fetch data from MT5"""
    if timeframe == 'H1':
        tf = mt5.TIMEFRAME_H1
    elif timeframe == 'D1':
        tf = mt5.TIMEFRAME_D1
    elif timeframe == 'W1':
        tf = mt5.TIMEFRAME_W1
    else:
        return None

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
    if rates is None or len(rates) == 0:
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')

    # Check if tick_volume exists and rename to volume (MT5 uses tick_volume)
    if 'tick_volume' in df.columns and 'volume' not in df.columns:
        df['volume'] = df['tick_volume']

    # Ensure volume column exists
    if 'volume' not in df.columns:
        print(f"   ⚠️ Warning: No volume data available, using dummy volume")
        df['volume'] = 1  # Dummy volume if not available

    return df


def analyze_confluence(signal_detector, h1_data, d1_data, w1_data, symbol, bar_index):
    """
    Analyze a specific bar to see confluence factors

    Returns: (signal, details_dict)
    """
    # Create temporary dataframes up to this bar
    temp_h1 = h1_data.iloc[:bar_index+1].copy()
    temp_d1 = d1_data.copy()
    temp_w1 = w1_data.copy()

    # Calculate VWAP on temp data
    temp_h1 = signal_detector.vwap.calculate(temp_h1)

    # Try to detect signal
    signal = signal_detector.detect_signal(
        current_data=temp_h1,
        daily_data=temp_d1,
        weekly_data=temp_w1,
        symbol=symbol
    )

    # Get current price and VWAP levels for analysis
    current_bar = temp_h1.iloc[-1]
    current_price = current_bar['close']

    details = {
        'time': current_bar['time'],
        'price': current_price,
        'vwap': current_bar.get('vwap', None),
        'vwap_upper_1': current_bar.get('vwap_upper_1', None),
        'vwap_lower_1': current_bar.get('vwap_lower_1', None),
        'vwap_upper_2': current_bar.get('vwap_upper_2', None),
        'vwap_lower_2': current_bar.get('vwap_lower_2', None),
    }

    return signal, details


def main():
    """Main diagnostic function"""
    print("\n" + "=" * 100)
    print("🔍 SIGNAL DIAGNOSTIC TOOL - Last 48 Hours Analysis")
    print("=" * 100)
    print()

    # Initialize MT5
    if not mt5.initialize():
        print("❌ Failed to initialize MT5")
        print("   Make sure MetaTrader 5 is running!")
        return

    print(f"✅ Connected to MT5")
    print(f"   Server time: {mt5.symbol_info_tick('EURUSD').time}")
    print(f"   BROKER_GMT_OFFSET: {BROKER_GMT_OFFSET} hours")
    print()

    # Initialize components
    signal_detector = SignalDetector()
    time_filter = TimeFilter()
    breakout_strategy = BreakoutStrategy()
    portfolio_manager = PortfolioManager()

    # Symbols to analyze
    symbols = ['EURUSD', 'GBPUSD']

    # Analyze each symbol
    for symbol in symbols:
        print("\n" + "=" * 100)
        print(f"📊 ANALYZING {symbol} - Last 48 Hours")
        print("=" * 100)

        # Fetch data
        print(f"\n📥 Fetching market data...")
        h1_data = get_mt5_data(symbol, 'H1', 200)
        d1_data = get_mt5_data(symbol, 'D1', 100)
        w1_data = get_mt5_data(symbol, 'W1', 50)

        if h1_data is None or d1_data is None or w1_data is None:
            print(f"❌ Failed to fetch data for {symbol}")
            continue

        print(f"   H1 bars: {len(h1_data)}")
        print(f"   D1 bars: {len(d1_data)}")
        print(f"   W1 bars: {len(w1_data)}")

        # Calculate VWAP
        h1_data = signal_detector.vwap.calculate(h1_data)

        # Calculate ATR for breakout detection
        high_low = h1_data['high'] - h1_data['low']
        high_close = abs(h1_data['high'] - h1_data['close'].shift())
        low_close = abs(h1_data['low'] - h1_data['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        h1_data['atr'] = true_range.rolling(window=14).mean()

        # Analyze last 48 bars (48 hours)
        now = datetime.now()
        cutoff_time = now - timedelta(hours=48)

        recent_bars = h1_data[h1_data['time'] >= cutoff_time]

        print(f"\n📊 Analyzing {len(recent_bars)} bars from last 48 hours...")
        print()

        signals_found = 0
        signals_blocked_by_time = 0
        signals_blocked_by_portfolio = 0
        bars_analyzed = 0

        # Track confluence scores
        confluence_scores = []

        for idx in range(len(h1_data) - len(recent_bars), len(h1_data)):
            bar = h1_data.iloc[idx]
            bar_time = bar['time']

            # Convert to datetime if needed
            if isinstance(bar_time, pd.Timestamp):
                bar_time = bar_time.to_pydatetime()

            # Skip if too old
            if bar_time < cutoff_time:
                continue

            bars_analyzed += 1

            # Get hour in GMT
            hour = bar_time.hour

            # Check time filters
            can_trade_mr = hour in MEAN_REVERSION_HOURS
            can_trade_bo = hour in BREAKOUT_HOURS

            # Check portfolio manager
            is_portfolio_tradeable = portfolio_manager.is_symbol_tradeable(symbol)

            # Analyze confluence
            signal, details = analyze_confluence(
                signal_detector, h1_data, d1_data, w1_data, symbol, idx
            )

            # Check for breakout signal
            breakout_signal = None
            if can_trade_bo:
                current_price = bar['close']
                current_volume = bar['volume']
                atr = h1_data['atr'].iloc[idx] if 'atr' in h1_data.columns else 0

                breakout_signal = breakout_strategy.detect_range_breakout(
                    data=h1_data.iloc[:idx+1],
                    current_price=current_price,
                    current_volume=current_volume,
                    atr=atr
                )

            # Record confluence score if signal was checked
            if signal:
                score = signal.get('confluence_score', 0)
                confluence_scores.append(score)

            # Report on this bar
            has_signal = signal is not None or breakout_signal is not None

            if has_signal:
                signal_type = "MEAN_REVERSION" if signal else "BREAKOUT"
                actual_signal = signal if signal else breakout_signal
                score = actual_signal.get('confluence_score', 0)

                # Check if it would have been blocked
                blocked_by_time = not (can_trade_mr or can_trade_bo)
                blocked_by_portfolio = not is_portfolio_tradeable

                if blocked_by_time:
                    signals_blocked_by_time += 1
                    status = "❌ BLOCKED BY TIME FILTER"
                elif blocked_by_portfolio:
                    signals_blocked_by_portfolio += 1
                    status = "❌ BLOCKED BY PORTFOLIO WINDOW"
                else:
                    signals_found += 1
                    status = "✅ SIGNAL WOULD EXECUTE"

                print(f"\n🎯 {status}")
                print(f"   Time: {bar_time.strftime('%Y-%m-%d %H:%M')} (Hour {hour})")
                print(f"   Type: {signal_type}")
                print(f"   Direction: {actual_signal.get('direction', 'N/A')}")
                print(f"   Confluence Score: {score} (min required: {MIN_CONFLUENCE_SCORE})")
                print(f"   Price: {details['price']:.5f}")
                print(f"   VWAP: {details['vwap']:.5f}")
                print(f"   Can trade MR: {can_trade_mr} (hour {hour} in {MEAN_REVERSION_HOURS})")
                print(f"   Can trade BO: {can_trade_bo} (hour {hour} in {BREAKOUT_HOURS})")
                print(f"   Portfolio allows: {is_portfolio_tradeable}")

                if signal:
                    factors = signal.get('factors', [])
                    print(f"   Confluence Factors: {', '.join(factors)}")

        # Summary for this symbol
        print(f"\n" + "-" * 100)
        print(f"📈 SUMMARY FOR {symbol}")
        print(f"-" * 100)
        print(f"Bars analyzed: {bars_analyzed}")
        print(f"Signals that would execute: {signals_found}")
        print(f"Signals blocked by time filter: {signals_blocked_by_time}")
        print(f"Signals blocked by portfolio window: {signals_blocked_by_portfolio}")

        if confluence_scores:
            print(f"\nConfluence scores observed:")
            print(f"   Average: {sum(confluence_scores) / len(confluence_scores):.1f}")
            print(f"   Max: {max(confluence_scores)}")
            print(f"   Min: {min(confluence_scores)}")
            print(f"   Scores >= {MIN_CONFLUENCE_SCORE}: {len([s for s in confluence_scores if s >= MIN_CONFLUENCE_SCORE])}")
        else:
            print(f"\n⚠️ NO confluence factors detected at all in last 48 hours")
            print(f"   This suggests:")
            print(f"   1. Price hasn't reached VWAP bands")
            print(f"   2. Price hasn't reached institutional levels (POC, VAH, VAL)")
            print(f"   3. Market is ranging in middle of VWAP bands")

    # Final summary
    print("\n\n" + "=" * 100)
    print("🔧 CONFIGURATION REVIEW")
    print("=" * 100)
    print(f"Minimum confluence score: {MIN_CONFLUENCE_SCORE}")
    print(f"Mean reversion hours (GMT): {MEAN_REVERSION_HOURS}")
    print(f"Breakout hours (GMT): {BREAKOUT_HOURS}")
    print(f"BROKER_GMT_OFFSET: {BROKER_GMT_OFFSET} hours")
    print()
    print("💡 TO RUN IN TEST MODE (trade all day, no time filters):")
    print("   python main.py --login XXX --password YYY --server ZZZ --test-mode")
    print()

    mt5.shutdown()


if __name__ == "__main__":
    main()
