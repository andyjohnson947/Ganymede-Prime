"""
Complete Trade Analysis - All 350 Trades
Detects grid, hedge, and DCA patterns
"""

import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import json

def load_all_trades(db_path='data/trading_data.db'):
    """Load all trades from database by reconstructing from deals"""
    conn = sqlite3.connect(db_path)

    # Load all deals
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
        print("❌ No deals found in database!")
        return pd.DataFrame()

    print(f"Found {len(deals_df)} deals in database")
    print(f"Unique position_ids: {deals_df['position_id'].nunique()}")
    print(f"Deals with NaN position_id: {deals_df['position_id'].isna().sum()}")
    print(f"\nEntry types distribution:")
    print(deals_df['entry'].value_counts())
    print(f"\nFirst few deals:")
    print(deals_df[['position_id', 'entry', 'type', 'symbol', 'volume', 'price']].head(10))

    deals_df['time'] = pd.to_datetime(deals_df['time'])

    # Reconstruct trades from deals
    # entry: 0=IN, 1=OUT, 2=INOUT, 3=OUT_BY
    trades = []
    skipped_no_entry = 0
    skipped_nan = 0

    print(f"\nReconstructing trades from deals...")

    for position_id in deals_df['position_id'].unique():
        if pd.isna(position_id):
            skipped_nan += 1
            continue

        position_deals = deals_df[deals_df['position_id'] == position_id].sort_values('time')

        # Get entry deal (entry=0 IN or entry=2 INOUT)
        entry_deals = position_deals[position_deals['entry'].isin([0, 2])]
        if entry_deals.empty:
            skipped_no_entry += 1
            continue

        entry_deal = entry_deals.iloc[0]

        # Get exit deal (entry=1 OUT or entry=2 INOUT or entry=3 OUT_BY)
        exit_deals = position_deals[position_deals['entry'].isin([1, 2, 3])]
        exit_deal = exit_deals.iloc[-1] if not exit_deals.empty else None

        # Convert type: 0=BUY, 1=SELL
        trade_type = 'buy' if entry_deal['type'] == 0 else 'sell'

        # Calculate total profit for position
        position_profit = position_deals['profit'].sum()
        position_commission = position_deals['commission'].sum()
        position_swap = position_deals['swap'].sum()

        trade = {
            'ticket': int(position_id),
            'position_id': int(position_id),
            'order': int(entry_deal['order']) if pd.notna(entry_deal['order']) else None,
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
            'stop_loss': None,
            'take_profit': None
        }

        trades.append(trade)

    print(f"\n✅ Reconstruction complete:")
    print(f"  Trades created: {len(trades)}")
    print(f"  Skipped (NaN position_id): {skipped_nan}")
    print(f"  Skipped (no entry deal): {skipped_no_entry}")

    trades_df = pd.DataFrame(trades)

    if not trades_df.empty:
        trades_df = trades_df.sort_values(['symbol', 'entry_time'])

    return trades_df

def detect_grid_patterns(trades_df):
    """
    Detect grid trading patterns
    Grid = multiple positions same direction with regular price spacing
    """
    grid_groups = []

    for symbol in trades_df['symbol'].unique():
        symbol_trades = trades_df[trades_df['symbol'] == symbol].copy()
        symbol_trades = symbol_trades.sort_values('entry_time')

        # Look for consecutive trades in same direction
        i = 0
        while i < len(symbol_trades):
            current = symbol_trades.iloc[i]
            grid_trades = [current]

            # Look ahead for similar trades
            j = i + 1
            while j < len(symbol_trades):
                next_trade = symbol_trades.iloc[j]

                # Check if same direction and within 24 hours
                time_diff = (next_trade['entry_time'] - current['entry_time']).total_seconds() / 3600

                if (next_trade['trade_type'] == current['trade_type'] and
                    time_diff < 24):
                    grid_trades.append(next_trade)
                    j += 1
                else:
                    break

            # If we found multiple trades in same direction, analyze spacing
            if len(grid_trades) >= 2:
                prices = [t['entry_price'] for t in grid_trades]
                spacings = [abs(prices[k+1] - prices[k]) for k in range(len(prices)-1)]
                avg_spacing = sum(spacings) / len(spacings) if spacings else 0
                spacing_std = pd.Series(spacings).std() if len(spacings) > 1 else 0

                # Regular spacing indicates grid (low std deviation)
                is_grid = spacing_std < avg_spacing * 0.3 if avg_spacing > 0 else False

                grid_groups.append({
                    'type': 'GRID' if is_grid else 'DCA',
                    'symbol': symbol,
                    'direction': current['trade_type'],
                    'trades': grid_trades,
                    'count': len(grid_trades),
                    'avg_spacing': avg_spacing,
                    'spacing_consistency': 'HIGH' if is_grid else 'LOW',
                    'total_volume': sum(t['volume'] for t in grid_trades),
                    'volume_pattern': 'INCREASING' if len(grid_trades) > 1 and grid_trades[-1]['volume'] > grid_trades[0]['volume'] else 'FLAT'
                })

            i = j if j > i + 1 else i + 1

    return grid_groups

def detect_hedge_patterns(trades_df):
    """
    Detect hedging patterns
    Hedge = opposite direction positions on same symbol within short time
    """
    hedge_groups = []

    for symbol in trades_df['symbol'].unique():
        symbol_trades = trades_df[trades_df['symbol'] == symbol].copy()
        symbol_trades = symbol_trades.sort_values('entry_time')

        # Look for opposite direction trades within 1 hour
        for i in range(len(symbol_trades)):
            for j in range(i + 1, len(symbol_trades)):
                trade1 = symbol_trades.iloc[i]
                trade2 = symbol_trades.iloc[j]

                time_diff = (trade2['entry_time'] - trade1['entry_time']).total_seconds() / 60

                # Hedge if opposite directions within 60 minutes
                if (trade1['trade_type'] != trade2['trade_type'] and
                    time_diff < 60 and
                    abs(trade1['entry_price'] - trade2['entry_price']) < trade1['entry_price'] * 0.01):  # Within 1%

                    hedge_groups.append({
                        'type': 'HEDGE',
                        'symbol': symbol,
                        'trade1': trade1,
                        'trade2': trade2,
                        'time_diff_minutes': time_diff,
                        'price_diff': abs(trade1['entry_price'] - trade2['entry_price']),
                        'volume_ratio': trade2['volume'] / trade1['volume'] if trade1['volume'] > 0 else 0
                    })

    return hedge_groups

def detect_dca_patterns(trades_df):
    """
    Detect Dollar Cost Averaging
    DCA = adding to losing position (same direction, later entry worse than first)
    """
    dca_groups = []

    for symbol in trades_df['symbol'].unique():
        symbol_trades = trades_df[trades_df['symbol'] == symbol].copy()
        symbol_trades = symbol_trades.sort_values('entry_time')

        i = 0
        while i < len(symbol_trades):
            current = symbol_trades.iloc[i]
            dca_trades = [current]

            # Look for adding to position (same direction, worse price)
            j = i + 1
            while j < len(symbol_trades):
                next_trade = symbol_trades.iloc[j]

                time_diff = (next_trade['entry_time'] - current['entry_time']).total_seconds() / 3600

                if (next_trade['trade_type'] == current['trade_type'] and
                    time_diff < 48):  # Within 48 hours

                    # Check if price is worse (DCA into loss)
                    if current['trade_type'] == 'buy':
                        is_worse = next_trade['entry_price'] < current['entry_price']
                    else:  # sell
                        is_worse = next_trade['entry_price'] > current['entry_price']

                    if is_worse:
                        dca_trades.append(next_trade)

                    j += 1
                else:
                    break

            if len(dca_trades) >= 2:
                dca_groups.append({
                    'type': 'DCA',
                    'symbol': symbol,
                    'direction': current['trade_type'],
                    'trades': dca_trades,
                    'count': len(dca_trades),
                    'total_volume': sum(t['volume'] for t in dca_trades),
                    'avg_volume': sum(t['volume'] for t in dca_trades) / len(dca_trades),
                    'price_range': abs(dca_trades[-1]['entry_price'] - dca_trades[0]['entry_price']),
                    'volume_increase': dca_trades[-1]['volume'] / dca_trades[0]['volume'] if dca_trades[0]['volume'] > 0 else 1
                })

            i = j if j > i + 1 else i + 1

    return dca_groups

def generate_comprehensive_report(trades_df):
    """Generate complete analysis report"""

    print("="*80)
    print("COMPLETE EA TRADE ANALYSIS")
    print("="*80)
    print()

    # Basic statistics
    print("📊 OVERALL STATISTICS")
    print("-" * 80)
    print(f"Total Trades: {len(trades_df)}")

    if trades_df.empty:
        print("\n❌ No trades found! Check database and reconstruction logic.")
        return

    print(f"Unique Symbols: {trades_df['symbol'].nunique()}")
    print(f"Date Range: {trades_df['entry_time'].min()} to {trades_df['entry_time'].max()}")
    print(f"Total Volume: {trades_df['volume'].sum():.2f} lots")
    print(f"Buy Trades: {(trades_df['trade_type'] == 'buy').sum()}")
    print(f"Sell Trades: {(trades_df['trade_type'] == 'sell').sum()}")

    # Profit analysis
    closed_trades = trades_df[trades_df['exit_time'].notna()]
    if len(closed_trades) > 0:
        print(f"\nClosed Trades: {len(closed_trades)}")
        print(f"Total Profit: ${closed_trades['profit'].sum():.2f}")
        print(f"Win Rate: {(closed_trades['profit'] > 0).sum() / len(closed_trades) * 100:.1f}%")
        print(f"Avg Profit per Trade: ${closed_trades['profit'].mean():.2f}")
    print()

    # Detect patterns
    print("🔍 PATTERN DETECTION")
    print("-" * 80)

    grid_patterns = detect_grid_patterns(trades_df)
    hedge_patterns = detect_hedge_patterns(trades_df)
    dca_patterns = detect_dca_patterns(trades_df)

    print(f"\n📐 GRID PATTERNS DETECTED: {len([g for g in grid_patterns if g['type'] == 'GRID'])}")
    print(f"💰 DCA PATTERNS DETECTED: {len(dca_patterns)}")
    print(f"⚖️  HEDGE PATTERNS DETECTED: {len(hedge_patterns)}")
    print()

    # Detailed grid analysis
    if grid_patterns:
        print("\n" + "="*80)
        print("GRID TRADING ANALYSIS")
        print("="*80)

        for idx, pattern in enumerate(grid_patterns, 1):
            print(f"\n[GRID-{idx:03d}] {pattern['symbol']} - {pattern['direction'].upper()}")
            print(f"  Type: {pattern['type']}")
            print(f"  Trades in Group: {pattern['count']}")
            print(f"  Total Volume: {pattern['total_volume']:.2f} lots")
            print(f"  Avg Price Spacing: {pattern['avg_spacing']:.5f}")
            print(f"  Spacing Consistency: {pattern['spacing_consistency']}")
            print(f"  Volume Pattern: {pattern['volume_pattern']}")
            print(f"  Trades:")
            for t in pattern['trades']:
                profit_str = f"${t['profit']:.2f}" if pd.notna(t['profit']) else "OPEN"
                print(f"    • Ticket {t['ticket']}: {t['entry_time']} @ {t['entry_price']:.5f} | Vol: {t['volume']:.2f} | P/L: {profit_str}")

    # Detailed hedge analysis
    if hedge_patterns:
        print("\n" + "="*80)
        print("HEDGE TRADING ANALYSIS")
        print("="*80)

        for idx, pattern in enumerate(hedge_patterns, 1):
            print(f"\n[HEDGE-{idx:03d}] {pattern['symbol']}")
            print(f"  Time Between Trades: {pattern['time_diff_minutes']:.1f} minutes")
            print(f"  Price Difference: {pattern['price_diff']:.5f}")
            print(f"  Volume Ratio: {pattern['volume_ratio']:.2f}x")
            print(f"  Trade 1: {pattern['trade1']['trade_type'].upper()} @ {pattern['trade1']['entry_price']:.5f} | {pattern['trade1']['volume']:.2f} lots")
            print(f"  Trade 2: {pattern['trade2']['trade_type'].upper()} @ {pattern['trade2']['entry_price']:.5f} | {pattern['trade2']['volume']:.2f} lots")

    # Detailed DCA analysis
    if dca_patterns:
        print("\n" + "="*80)
        print("DOLLAR COST AVERAGING ANALYSIS")
        print("="*80)

        for idx, pattern in enumerate(dca_patterns, 1):
            print(f"\n[DCA-{idx:03d}] {pattern['symbol']} - {pattern['direction'].upper()}")
            print(f"  Trades in Series: {pattern['count']}")
            print(f"  Total Volume: {pattern['total_volume']:.2f} lots")
            print(f"  Avg Volume per Trade: {pattern['avg_volume']:.2f} lots")
            print(f"  Price Range: {pattern['price_range']:.5f}")
            print(f"  Volume Increase Factor: {pattern['volume_increase']:.2f}x")
            print(f"  Trades:")
            for t in pattern['trades']:
                profit_str = f"${t['profit']:.2f}" if pd.notna(t['profit']) else "OPEN"
                print(f"    • Ticket {t['ticket']}: {t['entry_time']} @ {t['entry_price']:.5f} | Vol: {t['volume']:.2f} | P/L: {profit_str}")

    # Summary by symbol
    print("\n" + "="*80)
    print("SUMMARY BY SYMBOL")
    print("="*80)

    for symbol in sorted(trades_df['symbol'].unique()):
        sym_trades = trades_df[trades_df['symbol'] == symbol]
        sym_closed = sym_trades[sym_trades['exit_time'].notna()]

        print(f"\n{symbol}:")
        print(f"  Total Trades: {len(sym_trades)}")
        print(f"  Buy: {(sym_trades['trade_type'] == 'buy').sum()} | Sell: {(sym_trades['trade_type'] == 'sell').sum()}")

        if len(sym_closed) > 0:
            print(f"  Closed: {len(sym_closed)} | Profit: ${sym_closed['profit'].sum():.2f}")
            print(f"  Win Rate: {(sym_closed['profit'] > 0).sum() / len(sym_closed) * 100:.1f}%")

    # Export detailed CSV
    print("\n" + "="*80)
    print("EXPORTING DETAILED DATA")
    print("="*80)

    # Add reference IDs
    trades_export = trades_df.copy()
    trades_export['reference_id'] = ['TRD-' + str(i+1).zfill(4) for i in range(len(trades_export))]

    # Save to CSV
    output_file = 'all_350_trades_detailed.csv'
    trades_export.to_csv(output_file, index=False)
    print(f"✅ Exported all 350 trades with reference IDs to: {output_file}")

    # Save pattern summary
    pattern_summary = {
        'grid_patterns': len([g for g in grid_patterns if g['type'] == 'GRID']),
        'dca_patterns': len(dca_patterns),
        'hedge_patterns': len(hedge_patterns),
        'total_trades': len(trades_df),
        'analysis_date': datetime.now().isoformat()
    }

    with open('pattern_summary.json', 'w') as f:
        json.dump(pattern_summary, f, indent=2)
    print(f"✅ Pattern summary saved to: pattern_summary.json")

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)

if __name__ == '__main__':
    print("Loading all trades from database...")
    trades_df = load_all_trades()

    print(f"Loaded {len(trades_df)} trades")
    print()

    generate_comprehensive_report(trades_df)
