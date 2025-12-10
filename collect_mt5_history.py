#!/usr/bin/env python3
"""
Collect Trade History from MT5
Pulls all historical trades and saves for analysis
"""

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import sys


def connect_mt5(login=None, password=None, server=None):
    """Connect to MT5"""
    print("\n🔌 Connecting to MT5...")

    if not mt5.initialize():
        print(f"❌ MT5 initialization failed: {mt5.last_error()}")
        return False

    if login and password and server:
        authorized = mt5.login(login, password=password, server=server)
        if not authorized:
            print(f"❌ Login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False
        print(f"✅ Connected to account {login}")
    else:
        account_info = mt5.account_info()
        if account_info is None:
            print("❌ No account connected")
            return False
        print(f"✅ Connected to account {account_info.login}")

    return True


def collect_deals(from_date=None, to_date=None):
    """Collect all deals from MT5"""
    print("\n📥 Collecting deals from MT5...")

    if from_date is None:
        # Get last 90 days by default
        from_date = datetime.now() - timedelta(days=90)

    if to_date is None:
        to_date = datetime.now()

    print(f"   Date range: {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}")

    # Get all deals
    deals = mt5.history_deals_get(from_date, to_date)

    if deals is None:
        print(f"❌ No deals found: {mt5.last_error()}")
        return pd.DataFrame()

    if len(deals) == 0:
        print("⚠️  No deals found in this period")
        return pd.DataFrame()

    print(f"✅ Found {len(deals)} deals")

    # Convert to DataFrame
    deals_df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())

    # Convert timestamps
    deals_df['time'] = pd.to_datetime(deals_df['time'], unit='s')

    return deals_df


def reconstruct_trades(deals_df):
    """Reconstruct complete trades from deals"""
    print("\n🔄 Reconstructing trades...")

    # Filter out non-trade deals
    deals_df = deals_df[deals_df['entry'].isin([0, 1, 2])].copy()

    trades = []

    # Group by position_id
    for position_id in deals_df['position_id'].unique():
        if pd.isna(position_id) or position_id == 0:
            continue

        position_deals = deals_df[deals_df['position_id'] == position_id].sort_values('time')

        if position_deals.empty:
            continue

        # Entry deal
        entry_deals = position_deals[position_deals['entry'].isin([0, 2])]
        if entry_deals.empty:
            continue
        entry_deal = entry_deals.iloc[0]

        # Exit deal
        exit_deals = position_deals[position_deals['entry'].isin([1, 2])]
        exit_deal = exit_deals.iloc[-1] if not exit_deals.empty else None

        # Determine type
        trade_type = 'buy' if entry_deal['type'] == 0 else 'sell'

        # Calculate totals
        total_profit = position_deals['profit'].sum()
        total_commission = position_deals['commission'].sum()
        total_swap = position_deals['swap'].sum()

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
            'profit': float(total_profit),
            'commission': float(total_commission),
            'swap': float(total_swap),
            'magic_number': int(entry_deal['magic']) if pd.notna(entry_deal['magic']) else 0,
            'comment': str(entry_deal['comment']) if pd.notna(entry_deal['comment']) else '',
        }

        trades.append(trade)

    trades_df = pd.DataFrame(trades)

    if not trades_df.empty:
        trades_df = trades_df.sort_values('entry_time')

    print(f"✅ Reconstructed {len(trades_df)} complete trades")

    return trades_df


def save_to_csv(trades_df, output_file='ea_history.csv'):
    """Save trades to CSV"""
    print(f"\n💾 Saving to {output_file}...")

    trades_df.to_csv(output_file, index=False)

    print(f"✅ Saved {len(trades_df)} trades")
    print(f"\n📊 Summary:")
    print(f"   Symbols: {', '.join(trades_df['symbol'].unique())}")
    print(f"   Date range: {trades_df['entry_time'].min()} to {trades_df['entry_time'].max()}")
    print(f"   Total profit: ${trades_df['profit'].sum():.2f}")

    if 'magic_number' in trades_df.columns:
        magic_numbers = trades_df['magic_number'].unique()
        magic_numbers = [m for m in magic_numbers if m != 0]
        if magic_numbers:
            print(f"   Magic numbers: {', '.join(map(str, magic_numbers))}")


def main():
    """Main function"""
    print("=" * 80)
    print("MT5 TRADE HISTORY COLLECTOR")
    print("Collect all historical trades for DCA analysis")
    print("=" * 80)

    # Parse arguments
    login = None
    password = None
    server = None
    days = 90

    if len(sys.argv) > 1:
        if sys.argv[1] == '--help':
            print("\nUsage:")
            print("  python collect_mt5_history.py                    # Use current MT5 connection")
            print("  python collect_mt5_history.py LOGIN PASS SERVER  # Connect with credentials")
            print("  python collect_mt5_history.py --days 180         # Last 180 days")
            sys.exit(0)
        elif sys.argv[1] == '--days':
            days = int(sys.argv[2])
        elif len(sys.argv) >= 4:
            login = int(sys.argv[1])
            password = sys.argv[2]
            server = sys.argv[3]

    # Connect to MT5
    if not connect_mt5(login, password, server):
        sys.exit(1)

    try:
        # Collect deals
        from_date = datetime.now() - timedelta(days=days)
        deals_df = collect_deals(from_date)

        if deals_df.empty:
            print("\n❌ No deals found")
            sys.exit(1)

        # Reconstruct trades
        trades_df = reconstruct_trades(deals_df)

        if trades_df.empty:
            print("\n❌ No complete trades found")
            sys.exit(1)

        # Save to CSV
        save_to_csv(trades_df)

        print("\n" + "=" * 80)
        print("✅ COLLECTION COMPLETE")
        print("=" * 80)
        print("\nNext step:")
        print("  python import_and_analyze_dca.py ea_history.csv")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        mt5.shutdown()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Cancelled")
        mt5.shutdown()
        sys.exit(0)
