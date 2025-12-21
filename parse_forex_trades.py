#!/usr/bin/env python3
"""
Parse forex trading data from MT5 trade history format.
Converts tab-separated trade data into structured CSV format.
"""

import pandas as pd
from datetime import datetime
import sys
from pathlib import Path


def parse_trade_line(line: str) -> dict:
    """
    Parse a single line of trade data.

    Format: Symbol	Ticket	Timestamp	Type	Volume	EntryPrice	TP	SL	ExitPrice	Swap	Profit	Comment
    """
    parts = line.strip().split('\t')

    if len(parts) < 11:
        raise ValueError(f"Invalid line format: expected at least 11 fields, got {len(parts)}")

    return {
        'symbol': parts[0],
        'ticket': parts[1],
        'timestamp': parts[2],
        'trade_type': parts[3],
        'volume': float(parts[4]),
        'entry_price': float(parts[5]) if parts[5] else None,
        'tp': float(parts[6]) if parts[6] else None,
        'sl': float(parts[7]) if parts[7] else None,
        'exit_price': float(parts[8]) if parts[8] else None,
        'swap': float(parts[9]) if parts[9] else None,
        'profit': float(parts[10]) if parts[10] else None,
        'comment': parts[11] if len(parts) > 11 else ''
    }


def parse_forex_data(data_text: str) -> pd.DataFrame:
    """
    Parse forex trading data from text format.

    Args:
        data_text: Tab-separated trade data

    Returns:
        DataFrame with parsed trade data
    """
    lines = data_text.strip().split('\n')
    trades = []

    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue

        try:
            trade = parse_trade_line(line)
            trades.append(trade)
        except Exception as e:
            print(f"Warning: Failed to parse line {i}: {e}")
            continue

    df = pd.DataFrame(trades)

    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Sort by timestamp
    df = df.sort_values('timestamp')

    # Add derived fields
    df['trade_date'] = df['timestamp'].dt.date
    df['trade_time'] = df['timestamp'].dt.time
    df['trade_hour'] = df['timestamp'].dt.hour
    df['trade_day_of_week'] = df['timestamp'].dt.dayofweek

    # Identify hedge trades and related trades
    df['is_hedge'] = df['comment'].str.contains('H-', na=False)
    df['is_grid'] = df['comment'].str.contains('G', na=False)
    df['confluence_score'] = df['comment'].str.extract(r'Confluence:(\d+)', expand=False)
    df['related_ticket'] = df['comment'].str.extract(r'[HG]\d*-(\d+)', expand=False)

    return df


def analyze_trades(df: pd.DataFrame) -> dict:
    """
    Analyze trading patterns and performance.

    Args:
        df: DataFrame with trade data

    Returns:
        Dictionary with analysis results
    """
    analysis = {
        'total_trades': len(df),
        'total_profit': df['profit'].sum(),
        'winning_trades': len(df[df['profit'] > 0]),
        'losing_trades': len(df[df['profit'] < 0]),
        'break_even_trades': len(df[df['profit'] == 0]),
        'avg_profit_per_trade': df['profit'].mean(),
        'max_profit': df['profit'].max(),
        'max_loss': df['profit'].min(),
        'total_volume': df['volume'].sum(),
        'avg_volume': df['volume'].mean(),
    }

    # Symbol breakdown
    symbol_stats = df.groupby('symbol').agg({
        'profit': ['sum', 'mean', 'count'],
        'volume': 'sum'
    }).round(2)

    # Trade type breakdown
    type_stats = df.groupby('trade_type').agg({
        'profit': ['sum', 'mean', 'count'],
        'volume': 'sum'
    }).round(2)

    # Hedge trade analysis
    hedge_trades = df[df['is_hedge']]
    if len(hedge_trades) > 0:
        analysis['hedge_trades_count'] = len(hedge_trades)
        analysis['hedge_trades_profit'] = hedge_trades['profit'].sum()
        analysis['hedge_trades_avg_profit'] = hedge_trades['profit'].mean()

    # Confluence trades analysis
    confluence_trades = df[df['confluence_score'].notna()]
    if len(confluence_trades) > 0:
        analysis['confluence_trades_count'] = len(confluence_trades)
        analysis['confluence_trades_profit'] = confluence_trades['profit'].sum()
        analysis['avg_confluence_score'] = confluence_trades['confluence_score'].astype(float).mean()

    analysis['symbol_stats'] = symbol_stats
    analysis['type_stats'] = type_stats

    return analysis


def main():
    """Main function to parse forex trade data."""

    # Sample data provided by user
    sample_data = """EURUSD	6053051837	2025.12.19 20:43:09	buy	0.08	1.17216			1.17091	-0.06	-10.00	Confluence:17
GBPUSD	6053051970	2025.12.19 20:43:10	sell	0.08	1.33852			1.33776	-0.18	6.08	Confluence:7
EURUSD	6053065240	2025.12.19 20:44:11	buy	0.08	1.17223			1.17091	-0.06	-10.56	Confluence:17
GBPUSD	6053065302	2025.12.19 20:44:11	sell	0.08	1.33862			1.33776	-0.18	6.88	Confluence:7
EURUSD	6053078821	2025.12.19 20:45:12	buy	0.08	1.17219			1.17091	-0.06	-10.24	Confluence:17
GBPUSD	6053078956	2025.12.19 20:45:12	sell	0.08	1.33861			1.33776	-0.18	6.80	Confluence:7
EURUSD	6053096772	2025.12.19 20:46:13	buy	0.08	1.17218			1.17091	-0.06	-10.16	Confluence:17
GBPUSD	6053096838	2025.12.19 20:46:14	sell	0.08	1.33862			1.33776	-0.18	6.88	Confluence:7
EURUSD	6053110998	2025.12.19 20:47:14	buy	0.08	1.17217			1.17091	-0.06	-10.08	Confluence:17
GBPUSD	6053111120	2025.12.19 20:47:15	sell	0.08	1.33866			1.33776	-0.18	7.20	Confluence:7
EURUSD	6053124061	2025.12.19 20:48:15	buy	0.08	1.17220			1.17091	-0.06	-10.32	Confluence:17
GBPUSD	6053124150	2025.12.19 20:48:16	sell	0.08	1.33887			1.33776	-0.18	8.88	Confluence:7
GBPUSD	6053746358	2025.12.19 22:00:29	sell	0.04	1.33921			1.33776	-0.09	5.80
GBPUSD	6053746372	2025.12.19 22:00:29	buy	0.4	1.33925			1.33720	-0.08	-82.00	H-51970
GBPUSD	6053746381	2025.12.19 22:00:29	sell	0.04	1.33921			1.33776	-0.09	5.80
GBPUSD	6053746387	2025.12.19 22:00:29	buy	0.4	1.33925			1.33720	-0.08	-82.00	H-65302
GBPUSD	6053746405	2025.12.19 22:00:29	sell	0.04	1.33921			1.33776	-0.09	5.80
GBPUSD	6053746413	2025.12.19 22:00:29	buy	0.4	1.33925			1.33720	-0.08	-82.00	H-78956
GBPUSD	6053746424	2025.12.19 22:00:29	sell	0.04	1.33921			1.33776	-0.09	5.80
GBPUSD	6053746433	2025.12.19 22:00:29	buy	0.4	1.33925			1.33720	-0.08	-82.00	H-96838
GBPUSD	6053746447	2025.12.19 22:00:29	sell	0.04	1.33921			1.33776	-0.09	5.80
GBPUSD	6053746456	2025.12.19 22:00:30	buy	0.4	1.33925			1.33720	-0.08	-82.00	H-11120
GBPUSD	6053746505	2025.12.19 22:00:30	sell	0.04	1.33921			1.33776	-0.09	5.80
GBPUSD	6053746518	2025.12.19 22:00:30	buy	0.4	1.33925			1.33720	-0.08	-82.00	H-24150
GBPUSD	6053757195	2025.12.19 22:01:30	sell	0.06	1.33932			1.33776	-0.13	9.36
GBPUSD	6053757201	2025.12.19 22:01:30	sell	0.06	1.33932			1.33776	-0.13	9.36
GBPUSD	6053757216	2025.12.19 22:01:30	sell	0.06	1.33932			1.33776	-0.13	9.36
GBPUSD	6053757220	2025.12.19 22:01:30	sell	0.06	1.33932			1.33776	-0.13	9.36
GBPUSD	6053757229	2025.12.19 22:01:30	sell	0.06	1.33932			1.33776	-0.13	9.36
GBPUSD	6053757240	2025.12.19 22:01:31	sell	0.06	1.33932			1.33776	-0.13	9.36
GBPUSD	6054123046	2025.12.19 22:48:51	buy	0.08	1.33846			1.33720	-0.02	-10.08	G1-46372
GBPUSD	6054123066	2025.12.19 22:48:51	buy	0.08	1.33846			1.33720	-0.02	-10.08	G1-46387
GBPUSD	6054123103	2025.12.19 22:48:51	buy	0.08	1.33846			1.33720	-0.02	-10.08	G1-46413
GBPUSD	6054123120	2025.12.19 22:48:51	buy	0.08	1.33846			1.33720	-0.02	-10.08	G1-46433
GBPUSD	6054195865	2025.12.19 22:55:55	sell	0.2	1.33759			1.33776	-0.44	-3.40
GBPUSD	6054195903	2025.12.19 22:55:55	sell	0.2	1.33759			1.33776	-0.44	-3.40
GBPUSD	6054195915	2025.12.19 22:55:55	sell	0.4	1.33755			1.33776	-0.88	-8.40	H-23103
GBPUSD	6054195934	2025.12.19 22:55:55	sell	0.4	1.33755			1.33776	-0.88	-8.40	H-231"""

    # Parse the data
    print("Parsing forex trade data...")
    df = parse_forex_data(sample_data)

    # Save to CSV
    output_file = 'parsed_trades.csv'
    df.to_csv(output_file, index=False)
    print(f"\n✓ Saved {len(df)} trades to {output_file}")

    # Analyze trades
    print("\n" + "="*60)
    print("TRADE ANALYSIS")
    print("="*60)

    analysis = analyze_trades(df)

    print(f"\nOverall Performance:")
    print(f"  Total Trades: {analysis['total_trades']}")
    print(f"  Total Profit: ${analysis['total_profit']:.2f}")
    print(f"  Winning Trades: {analysis['winning_trades']} ({analysis['winning_trades']/analysis['total_trades']*100:.1f}%)")
    print(f"  Losing Trades: {analysis['losing_trades']} ({analysis['losing_trades']/analysis['total_trades']*100:.1f}%)")
    print(f"  Average Profit/Trade: ${analysis['avg_profit_per_trade']:.2f}")
    print(f"  Max Profit: ${analysis['max_profit']:.2f}")
    print(f"  Max Loss: ${analysis['max_loss']:.2f}")
    print(f"  Total Volume: {analysis['total_volume']:.2f} lots")

    if 'hedge_trades_count' in analysis:
        print(f"\nHedge Trades:")
        print(f"  Count: {analysis['hedge_trades_count']}")
        print(f"  Total Profit: ${analysis['hedge_trades_profit']:.2f}")
        print(f"  Average Profit: ${analysis['hedge_trades_avg_profit']:.2f}")

    if 'confluence_trades_count' in analysis:
        print(f"\nConfluence Trades:")
        print(f"  Count: {analysis['confluence_trades_count']}")
        print(f"  Total Profit: ${analysis['confluence_trades_profit']:.2f}")
        print(f"  Average Confluence Score: {analysis['avg_confluence_score']:.1f}")

    print(f"\nBy Symbol:")
    print(analysis['symbol_stats'])

    print(f"\nBy Trade Type:")
    print(analysis['type_stats'])

    # Show sample of parsed data
    print("\n" + "="*60)
    print("SAMPLE PARSED DATA (first 5 trades)")
    print("="*60)
    print(df[['symbol', 'timestamp', 'trade_type', 'volume', 'entry_price', 'profit', 'comment']].head())

    return df


if __name__ == '__main__':
    main()
