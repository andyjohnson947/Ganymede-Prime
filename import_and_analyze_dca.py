#!/usr/bin/env python3
"""
Import Trade Data and Analyze DCA Settings
Quickly analyze your historical trades to find optimal DCA parameters
"""

import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path
from datetime import datetime
import sys


def import_csv_trades(csv_path):
    """
    Import trades from CSV file

    Expected CSV columns:
    - Symbol, Position, Time, Type, Volume, Price, Market Price, S/L, T/P,
      Swap, Profit, Comment

    Or drag-and-drop from MT5:
    - Login, Order, Symbol, Type, Volume, Open Price, S/L, T/P, Open Time,
      Close Time, Close Price, Commission, Swap, Profit, Comment
    """
    print(f"\n📥 Importing trades from: {csv_path}")

    df = pd.read_csv(csv_path)
    print(f"✅ Loaded {len(df)} rows from CSV")

    # Show column names to help user map
    print(f"\nColumns found: {list(df.columns)}")

    # Try to standardize column names
    column_mapping = {
        # MT5 standard export
        'Order': 'ticket',
        'Position': 'position_id',
        'Symbol': 'symbol',
        'Type': 'trade_type',
        'Volume': 'volume',
        'Open Price': 'entry_price',
        'Price': 'entry_price',
        'Close Price': 'exit_price',
        'Market Price': 'exit_price',
        'Open Time': 'entry_time',
        'Time': 'entry_time',
        'Close Time': 'exit_time',
        'S / L': 'sl',
        'S/L': 'sl',
        'T / P': 'tp',
        'T/P': 'tp',
        'Swap': 'swap',
        'Profit': 'profit',
        'Comment': 'comment',
        'Commission': 'commission',
    }

    # Rename columns
    df = df.rename(columns=column_mapping)

    # Convert trade type to 'buy'/'sell'
    if 'trade_type' in df.columns:
        df['trade_type'] = df['trade_type'].str.lower()
        df['trade_type'] = df['trade_type'].replace({
            'buy': 'buy',
            'sell': 'sell',
            '0': 'buy',
            '1': 'sell',
            'balance': None,  # Filter out balance operations
        })
        df = df[df['trade_type'].isin(['buy', 'sell'])].copy()

    # Convert time columns
    for time_col in ['entry_time', 'exit_time']:
        if time_col in df.columns:
            df[time_col] = pd.to_datetime(df[time_col], errors='coerce')

    # Fill missing position_id with ticket
    if 'position_id' not in df.columns and 'ticket' in df.columns:
        df['position_id'] = df['ticket']

    print(f"✅ Cleaned data: {len(df)} valid trades")

    return df


def create_database(trades_df, db_path='data/trading_data.db'):
    """Create SQLite database from trades"""
    print(f"\n💾 Creating database: {db_path}")

    # Create data directory
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)

    # Create deals table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS historical_deals (
            ticket INTEGER,
            [order] INTEGER,
            position_id INTEGER,
            time TEXT,
            type INTEGER,
            entry INTEGER,
            symbol TEXT,
            volume REAL,
            price REAL,
            profit REAL,
            commission REAL,
            swap REAL,
            magic INTEGER,
            comment TEXT
        )
    """)

    # Convert trades to deals format
    deals = []
    for _, trade in trades_df.iterrows():
        # Entry deal
        deals.append({
            'ticket': trade.get('ticket', trade.get('position_id')),
            'order': trade.get('ticket', trade.get('position_id')),
            'position_id': trade.get('position_id'),
            'time': trade['entry_time'].isoformat() if pd.notna(trade.get('entry_time')) else None,
            'type': 0 if trade['trade_type'] == 'buy' else 1,
            'entry': 0,  # Entry deal
            'symbol': trade.get('symbol', ''),
            'volume': trade.get('volume', 0),
            'price': trade.get('entry_price', 0),
            'profit': 0,  # Profit only on exit
            'commission': 0,
            'swap': 0,
            'magic': trade.get('magic_number'),
            'comment': trade.get('comment', ''),
        })

        # Exit deal (if closed)
        if pd.notna(trade.get('exit_time')):
            deals.append({
                'ticket': trade.get('ticket', trade.get('position_id')),
                'order': trade.get('ticket', trade.get('position_id')),
                'position_id': trade.get('position_id'),
                'time': trade['exit_time'].isoformat(),
                'type': 1 if trade['trade_type'] == 'buy' else 0,  # Opposite
                'entry': 1,  # Exit deal
                'symbol': trade.get('symbol', ''),
                'volume': trade.get('volume', 0),
                'price': trade.get('exit_price', 0),
                'profit': trade.get('profit', 0),
                'commission': trade.get('commission', 0),
                'swap': trade.get('swap', 0),
                'magic': trade.get('magic_number'),
                'comment': trade.get('comment', ''),
            })

    deals_df = pd.DataFrame(deals)
    deals_df.to_sql('historical_deals', conn, if_exists='replace', index=False)

    conn.commit()
    conn.close()

    print(f"✅ Database created with {len(deals)} deals ({len(trades_df)} trades)")


def analyze_dca_quick(trades_df):
    """Quick DCA analysis without full script"""
    print("\n" + "=" * 80)
    print("💰 QUICK DCA ANALYSIS")
    print("=" * 80)

    # Add default symbol if missing
    if 'symbol' not in trades_df.columns:
        trades_df['symbol'] = 'UNKNOWN'
        print("⚠️  No 'symbol' column found - treating all trades as same symbol")

    # Sort by symbol and time
    trades_df = trades_df.sort_values(['symbol', 'entry_time'])

    # Detect DCA sequences (same direction, adding to losing position)
    dca_sequences = []

    for symbol in trades_df['symbol'].unique():
        symbol_trades = trades_df[trades_df['symbol'] == symbol].copy()

        i = 0
        while i < len(symbol_trades):
            current = symbol_trades.iloc[i]
            dca_trades = [current]

            # Look for consecutive same-direction trades
            j = i + 1
            while j < len(symbol_trades):
                next_trade = symbol_trades.iloc[j]

                # Same direction within 48 hours
                time_diff = (next_trade['entry_time'] - current['entry_time']).total_seconds() / 3600
                if time_diff > 48:
                    break

                if next_trade['trade_type'] == current['trade_type']:
                    # Check if adding to losing position
                    if current['trade_type'] == 'buy':
                        is_worse = next_trade['entry_price'] < current['entry_price']
                    else:
                        is_worse = next_trade['entry_price'] > current['entry_price']

                    if is_worse:
                        dca_trades.append(next_trade)

                j += 1

            if len(dca_trades) >= 2:
                volumes = [t['volume'] for t in dca_trades]
                prices = [t['entry_price'] for t in dca_trades]

                # Calculate multipliers
                multipliers = [volumes[k+1] / volumes[k] for k in range(len(volumes)-1)]
                avg_multiplier = np.mean(multipliers)

                # Calculate profit
                total_profit = sum(t.get('profit', 0) for t in dca_trades)

                dca_sequences.append({
                    'symbol': symbol,
                    'levels': len(dca_trades),
                    'avg_multiplier': avg_multiplier,
                    'total_profit': total_profit,
                    'successful': total_profit > 0,
                    'start_price': prices[0],
                    'end_price': prices[-1],
                    'decline_pips': abs(prices[-1] - prices[0]) * 10000,
                })

            i = j if j > i + 1 else i + 1

    if not dca_sequences:
        print("\n⚠️  No DCA sequences detected")
        print("This could mean:")
        print("  • No repeated entries on same symbol")
        print("  • No averaging down detected")
        print("  • Check if Comment field contains 'DCA' markers")
        return

    print(f"\n✅ Found {len(dca_sequences)} DCA sequences")

    # Analyze by depth
    print("\n📊 Success Rate by DCA Depth:")
    print("-" * 60)
    for depth in range(2, 10):
        depth_seqs = [s for s in dca_sequences if s['levels'] == depth]
        if depth_seqs:
            successful = len([s for s in depth_seqs if s['successful']])
            success_rate = (successful / len(depth_seqs)) * 100
            avg_profit = np.mean([s['total_profit'] for s in depth_seqs])
            avg_multiplier = np.mean([s['avg_multiplier'] for s in depth_seqs])

            status = "✅" if success_rate > 60 else "⚠️" if success_rate > 40 else "❌"
            print(f"{status} {depth} levels: {success_rate:.1f}% win rate "
                  f"({successful}/{len(depth_seqs)}) | "
                  f"Avg P/L: ${avg_profit:.2f} | "
                  f"Multiplier: {avg_multiplier:.2f}x")

    # Overall stats
    print("\n📈 Overall DCA Statistics:")
    print("-" * 60)
    successful = len([s for s in dca_sequences if s['successful']])
    print(f"Total DCA sequences: {len(dca_sequences)}")
    print(f"Successful: {successful} ({successful/len(dca_sequences)*100:.1f}%)")
    print(f"Average levels: {np.mean([s['levels'] for s in dca_sequences]):.1f}")
    print(f"Average multiplier: {np.mean([s['avg_multiplier'] for s in dca_sequences]):.2f}x")
    print(f"Average profit: ${np.mean([s['total_profit'] for s in dca_sequences]):.2f}")

    # Best performers
    print("\n🏆 Best DCA Sequences:")
    print("-" * 60)
    best = sorted(dca_sequences, key=lambda x: x['total_profit'], reverse=True)[:5]
    for idx, seq in enumerate(best, 1):
        print(f"{idx}. {seq['symbol']}: {seq['levels']} levels, "
              f"${seq['total_profit']:.2f}, "
              f"{seq['avg_multiplier']:.2f}x multiplier")

    # Worst performers
    print("\n⚠️  Worst DCA Sequences:")
    print("-" * 60)
    worst = sorted(dca_sequences, key=lambda x: x['total_profit'])[:5]
    for idx, seq in enumerate(worst, 1):
        print(f"{idx}. {seq['symbol']}: {seq['levels']} levels, "
              f"${seq['total_profit']:.2f}, "
              f"{seq['decline_pips']:.1f} pips decline")

    # Recommendations
    print("\n" + "=" * 80)
    print("💡 RECOMMENDATIONS")
    print("=" * 80)

    # Find best depth
    best_depth = None
    best_rate = 0
    for depth in range(2, 10):
        depth_seqs = [s for s in dca_sequences if s['levels'] == depth]
        if len(depth_seqs) >= 3:
            success_rate = len([s for s in depth_seqs if s['successful']]) / len(depth_seqs) * 100
            if success_rate > best_rate:
                best_rate = success_rate
                best_depth = depth

    if best_depth:
        print(f"\n✅ Optimal DCA Depth: {best_depth} levels ({best_rate:.1f}% success rate)")
        optimal_seqs = [s for s in dca_sequences if s['levels'] == best_depth]
        optimal_mult = np.mean([s['avg_multiplier'] for s in optimal_seqs])
        print(f"✅ Recommended Multiplier: {optimal_mult:.2f}x")
    else:
        print("\n⚠️  Need more data for reliable recommendations")

    overall_success = successful / len(dca_sequences) * 100
    if overall_success < 50:
        print("\n❌ WARNING: DCA strategy is losing overall!")
        print("   Consider:")
        print("   • Reducing max DCA levels")
        print("   • Lowering lot multiplier")
        print("   • Tightening entry conditions")


def main():
    """Main entry point"""
    print("=" * 80)
    print("DCA SETTINGS ANALYZER")
    print("Import your MT5 trade history and find optimal DCA parameters")
    print("=" * 80)

    if len(sys.argv) < 2:
        print("\n❌ Usage: python import_and_analyze_dca.py <path_to_csv>")
        print("\nHow to export from MT5:")
        print("1. Open MT5 terminal")
        print("2. Go to 'Account History' tab")
        print("3. Right-click → 'Save as Report'")
        print("4. Choose 'Open XML' or 'CSV' format")
        print("5. Run: python import_and_analyze_dca.py trades.csv")
        sys.exit(1)

    csv_path = sys.argv[1]

    if not Path(csv_path).exists():
        print(f"\n❌ File not found: {csv_path}")
        sys.exit(1)

    # Import trades
    trades_df = import_csv_trades(csv_path)

    if trades_df.empty:
        print("\n❌ No valid trades found in CSV")
        sys.exit(1)

    # Quick analysis
    analyze_dca_quick(trades_df)

    # Create database for full analysis
    print("\n" + "=" * 80)
    print("💾 Saving data for comprehensive analysis...")
    print("=" * 80)

    try:
        create_database(trades_df)
        print("\n✅ Database created: data/trading_data.db")
        print("\nNext steps:")
        print("1. Run: python analyze_recovery_strategies.py")
        print("2. Review: recovery_strategy_analysis.json")
    except Exception as e:
        print(f"\n⚠️  Could not create database: {e}")

    print("\n✅ Analysis complete!")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Cancelled")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
