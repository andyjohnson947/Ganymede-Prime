#!/usr/bin/env python3
"""
Multi-Timeframe EA Analysis
Extends EA reverse engineering with multi-timeframe LVN, session volatility,
weekly levels, recovery tracking, and time-based patterns
"""

import sys
from pathlib import Path
import pandas as pd
import sqlite3
import json
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.bot import MT5TradingBot
from src.utils import load_config, load_credentials, setup_logging
from src.ea_mining.multi_timeframe_analyzer import MultiTimeframeAnalyzer


def load_market_data_from_db(symbol='EURUSD', timeframe='H1', db_path='data/trading_data.db'):
    """Load market data from database first"""
    print(f"\n📥 Loading {symbol} {timeframe} data from database...")

    try:
        if not Path(db_path).exists():
            print(f"⚠️  Database not found: {db_path}")
            return None

        conn = sqlite3.connect(db_path)

        query = """
        SELECT time, open, high, low, close, tick_volume, spread, real_volume
        FROM price_data
        WHERE symbol = ? AND timeframe = ?
        ORDER BY time
        """

        df = pd.read_sql_query(query, conn, params=(symbol, timeframe))
        conn.close()

        if not df.empty:
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
            print(f"✅ Loaded {len(df)} bars from database")
            return df
        else:
            print(f"⚠️  No data found in database for {symbol} {timeframe}")
            return None

    except Exception as e:
        print(f"❌ Error loading from database: {e}")
        return None


def load_market_data_from_mt5(symbol='EURUSD', timeframe='H1', bars=10000, start_date=None):
    """Load historical market data from MT5"""

    try:
        from src.mt5_connection import MT5ConnectionManager

        config = load_config()
        credentials = load_credentials()

        # Create MT5 connection
        mt5_manager = MT5ConnectionManager(credentials['mt5'])

        if not mt5_manager.connect():
            print("❌ Failed to connect to MT5")
            return None

        # If we have a specific start date, use date range method
        if start_date:
            print(f"\n📥 Loading {symbol} {timeframe} from {start_date} to now...")
            end_date = datetime.now()
            data = mt5_manager.get_historical_data(
                symbol,
                timeframe,
                bars=bars,
                start_date=start_date,
                end_date=end_date
            )
        else:
            print(f"\n📥 Loading {bars} bars of {symbol} {timeframe} from MT5...")
            data = mt5_manager.get_historical_data(symbol, timeframe, bars=bars)

        mt5_manager.disconnect()

        if data is not None and not data.empty:
            print(f"✅ Loaded {len(data)} bars from MT5")
            print(f"   Data range: {data.index.min()} to {data.index.max()}")
            return data
        else:
            print("❌ No data returned from MT5")
            return None

    except Exception as e:
        print(f"❌ Error loading market data: {e}")
        import traceback
        traceback.print_exc()
        return None


def load_market_data(symbol='EURUSD', timeframe='H1', bars=10000, start_date=None):
    """Load market data - try database first, then MT5"""

    # Try database first (faster)
    data = load_market_data_from_db(symbol, timeframe)

    if data is not None and len(data) >= 1000:
        # Check if database data covers the start_date
        if start_date and data.index.min() > pd.to_datetime(start_date):
            print(f"\n⚠️  Database data starts at {data.index.min()}")
            print(f"   But we need data from {start_date}")
            print("📡 Loading from MT5 instead...")
            return load_market_data_from_mt5(symbol, timeframe, bars, start_date)
        return data

    # Fall back to MT5
    print("\n📡 Database insufficient, loading from MT5...")
    return load_market_data_from_mt5(symbol, timeframe, bars, start_date)


def load_trades_from_db(db_path='data/trading_data.db'):
    """Load trades from database"""
    print(f"\n📥 Loading trades from database...")

    try:
        if not Path(db_path).exists():
            print(f"❌ Database not found: {db_path}")
            return pd.DataFrame()

        conn = sqlite3.connect(db_path)

        # Load deals and reconstruct trades
        query = """
        SELECT
            ticket,
            [order],
            position_id,
            time,
            type,
            entry,
            symbol,
            volume,
            price,
            profit,
            commission,
            swap,
            magic,
            comment
        FROM historical_deals
        ORDER BY position_id, time
        """

        deals_df = pd.read_sql_query(query, conn)
        conn.close()

        if deals_df.empty:
            print("❌ No deals found in database")
            return pd.DataFrame()

        print(f"Found {len(deals_df)} deals")

        # Reconstruct trades from deals
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

            # Convert type: 0=BUY, 1=SELL
            trade_type = 'buy' if entry_deal['type'] == 0 else 'sell'

            # Calculate total profit
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
            print(f"✅ Reconstructed {len(trades_df)} trades")

        return trades_df

    except Exception as e:
        print(f"❌ Error loading trades: {e}")
        return pd.DataFrame()


def detect_recovery_patterns(trades_df):
    """Detect DCA/recovery patterns from trades"""
    print("\n🔍 Detecting recovery patterns...")

    recovery_patterns = []

    for symbol in trades_df['symbol'].unique():
        symbol_trades = trades_df[trades_df['symbol'] == symbol].copy()
        symbol_trades = symbol_trades.sort_values('entry_time')

        i = 0
        while i < len(symbol_trades):
            current = symbol_trades.iloc[i]
            recovery_trades = [current.to_dict()]

            # Look for adding to position (same direction)
            j = i + 1
            while j < len(symbol_trades):
                next_trade = symbol_trades.iloc[j]

                time_diff = (next_trade['entry_time'] - current['entry_time']).total_seconds() / 3600

                if (next_trade['trade_type'] == current['trade_type'] and time_diff < 48):
                    # Check if price is worse (recovery into loss)
                    if current['trade_type'] == 'buy':
                        is_worse = next_trade['entry_price'] < current['entry_price']
                    else:
                        is_worse = next_trade['entry_price'] > current['entry_price']

                    if is_worse:
                        recovery_trades.append(next_trade.to_dict())

                    j += 1
                else:
                    break

            if len(recovery_trades) >= 2:
                recovery_patterns.append({
                    'type': 'RECOVERY',
                    'symbol': symbol,
                    'direction': current['trade_type'],
                    'trades': recovery_trades,
                    'count': len(recovery_trades),
                    'total_volume': sum(t['volume'] for t in recovery_trades),
                })

            i = j if j > i + 1 else i + 1

    print(f"✅ Found {len(recovery_patterns)} recovery patterns")

    return recovery_patterns


def main():
    """Main analysis function"""
    print("=" * 80)
    print("MULTI-TIMEFRAME EA ANALYSIS")
    print("=" * 80)

    # Load trades first to check date range
    trades_df = load_trades_from_db()

    start_date = None
    bars_needed = 10000

    if not trades_df.empty:
        print(f"\n📊 Found {len(trades_df)} trades")
        earliest_trade = trades_df['entry_time'].min()
        latest_trade = trades_df['entry_time'].max()
        print(f"   Trade date range: {earliest_trade} to {latest_trade}")

        # Add 30 days buffer before earliest trade for analysis context
        start_date = earliest_trade - timedelta(days=30)

        # Calculate bars needed from start_date to now
        days_range = (datetime.now() - start_date).days
        bars_needed = max(10000, int(days_range * 24 * 1.2))  # 20% buffer

        print(f"   Loading data from: {start_date.date()} (30 days before earliest trade)")
        print(f"   Estimated bars needed: {bars_needed:,}")
    else:
        print("\n⚠️  No trades found - analysis will be limited to market data only")

    # Load market data with sufficient coverage
    print(f"\n📊 Requesting data:")
    print(f"   Start date: {start_date if start_date else 'Not specified'}")
    print(f"   Bars requested: {bars_needed:,}")
    print(f"   Symbol: EURUSD")
    print(f"   Timeframe: H1")

    market_data = load_market_data(
        symbol='EURUSD',
        timeframe='H1',
        bars=bars_needed,
        start_date=start_date
    )

    if market_data is None:
        print("\n❌ Cannot proceed without market data")
        sys.exit(1)

    actual_bars = len(market_data)
    print(f"\n📊 Actually received: {actual_bars:,} bars")
    if actual_bars < bars_needed:
        print(f"   ⚠️  Received {bars_needed - actual_bars:,} fewer bars than requested")
        print(f"   This may be due to broker data availability limits")

    # Check data coverage and retry if needed
    if not trades_df.empty:
        data_start = market_data.index.min()
        data_end = market_data.index.max()
        print(f"\n📈 Market data range: {data_start} to {data_end}")

        # Check if we have coverage
        trades_outside = trades_df[
            (trades_df['entry_time'] < data_start) |
            (trades_df['entry_time'] > data_end)
        ]

        if len(trades_outside) > 0:
            print(f"\n⚠️  WARNING: {len(trades_outside)} trades are outside market data range")

            # Find the earliest trade that's outside
            earliest_outside = trades_outside[
                trades_outside['entry_time'] < data_start
            ]

            if len(earliest_outside) > 0:
                earliest_needed = earliest_outside['entry_time'].min()
                print(f"   Earliest uncovered trade: {earliest_needed}")
                print(f"   Current data starts at: {data_start}")

                # Try to load more data with extended start date
                extended_start = earliest_needed - timedelta(days=30)
                days_to_load = (datetime.now() - extended_start).days
                # Request MORE bars to account for weekends/holidays
                extended_bars = int(days_to_load * 24 * 1.5)  # 50% buffer instead of 20%

                print(f"\n📥 RETRY: Attempting to load more data from {extended_start.date()}...")
                print(f"   Target: Cover from {extended_start.date()} to now")
                print(f"   Days span: {days_to_load}")
                print(f"   Requesting {extended_bars:,} bars (1.5x factor for weekends)")

                extended_data = load_market_data_from_mt5(
                    symbol='EURUSD',
                    timeframe='H1',
                    bars=extended_bars,
                    start_date=extended_start
                )

                if extended_data is not None and not extended_data.empty:
                    if extended_data.index.min() <= earliest_needed:
                        market_data = extended_data
                        data_start = market_data.index.min()
                        data_end = market_data.index.max()
                        print(f"✅ Successfully extended data range!")
                        print(f"   New range: {data_start} to {data_end}")

                        # Recheck coverage
                        trades_outside = trades_df[
                            (trades_df['entry_time'] < data_start) |
                            (trades_df['entry_time'] > data_end)
                        ]

            if len(trades_outside) > 0:
                print(f"\n⚠️  Still have {len(trades_outside)} trades outside data range")
                print(f"   MT5 may not have enough historical data available")
                print(f"   Analysis will proceed with {len(trades_df) - len(trades_outside)} trades")
            else:
                print(f"\n✅ All {len(trades_df)} trades are now within market data range!")
        else:
            print(f"\n✅ All {len(trades_df)} trades are within market data range")

    # Filter trades to only those within data range
    if not trades_df.empty:
        original_count = len(trades_df)
        trades_df = trades_df[
            (trades_df['entry_time'] >= market_data.index.min()) &
            (trades_df['entry_time'] <= market_data.index.max())
        ]
        if len(trades_df) < original_count:
            print(f"\n📊 Analyzing {len(trades_df)} trades within data range")
            print(f"   ({original_count - len(trades_df)} trades excluded due to insufficient data)")

    # Detect recovery patterns
    recovery_patterns = []
    if not trades_df.empty:
        recovery_patterns = detect_recovery_patterns(trades_df)

    # Initialize analyzer
    analyzer = MultiTimeframeAnalyzer()

    # Generate comprehensive report
    print("\n" + "=" * 80)
    print("RUNNING MULTI-TIMEFRAME ANALYSIS")
    print("=" * 80)

    report = analyzer.generate_comprehensive_report(
        market_data=market_data,
        trades_df=trades_df,
        recovery_patterns=recovery_patterns
    )

    # Print summary
    analyzer.print_analysis_summary(report)

    # Save report to JSON
    output_file = 'multi_timeframe_analysis.json'
    with open(output_file, 'w') as f:
        # Convert numpy types to native Python types for JSON serialization
        def convert_types(obj):
            if isinstance(obj, dict):
                return {k: convert_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_types(i) for i in obj]
            elif hasattr(obj, 'item'):
                return obj.item()
            elif pd.isna(obj):
                return None
            else:
                return obj

        json.dump(convert_types(report), f, indent=2, default=str)

    print(f"\n✅ Detailed report saved to: {output_file}")

    # Save summary CSV
    summary_data = []

    # Add LVN levels
    for tf, levels in report.get('lvn_multi_timeframe', {}).items():
        if levels:
            summary_data.append({
                'category': 'LVN_Levels',
                'timeframe': tf,
                'metric': 'POC',
                'value': levels.get('poc', 0)
            })
            summary_data.append({
                'category': 'LVN_Levels',
                'timeframe': tf,
                'metric': 'VAH',
                'value': levels.get('vah', 0)
            })
            summary_data.append({
                'category': 'LVN_Levels',
                'timeframe': tf,
                'metric': 'VAL',
                'value': levels.get('val', 0)
            })

    # Add session volatility
    for session, stats in report.get('session_volatility', {}).items():
        summary_data.append({
            'category': 'Session_Volatility',
            'timeframe': session,
            'metric': 'Avg_ATR',
            'value': stats.get('avg_atr', 0)
        })
        summary_data.append({
            'category': 'Session_Volatility',
            'timeframe': session,
            'metric': 'Volatility_Rank',
            'value': stats.get('volatility_rank', 0)
        })

    # Add time-based best hours
    for idx, time_info in enumerate(report.get('time_based_patterns', {}).get('best_times', []), 1):
        summary_data.append({
            'category': 'Best_Times',
            'timeframe': f"Rank_{idx}",
            'metric': f"Hour_{time_info['hour']:02d}",
            'value': time_info['win_rate']
        })

    if summary_data:
        summary_df = pd.DataFrame(summary_data)
        summary_file = 'multi_timeframe_summary.csv'
        summary_df.to_csv(summary_file, index=False)
        print(f"✅ Summary CSV saved to: {summary_file}")

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
