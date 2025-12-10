#!/usr/bin/env python3
"""
Quick diagnostic to check what symbols are in the trades database
"""
import sqlite3
import pandas as pd
from pathlib import Path

db_path = Path("data/trading_data.db")

if not db_path.exists():
    print(f"❌ Database not found at: {db_path}")
    exit(1)

print(f"📊 Checking database: {db_path}\n")

conn = sqlite3.connect(db_path)

# Check if ea_trades table exists
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]

print(f"Tables in database: {tables}\n")

if 'ea_trades' not in tables:
    print("❌ ea_trades table not found!")
    print("\nLet me check deals table instead...\n")

    # Check historical_deals table
    if 'historical_deals' in tables:
        print("📊 Checking historical_deals table:")
        deals_df = pd.read_sql("SELECT ticket, symbol, time, price, volume FROM historical_deals LIMIT 10", conn)
        print(deals_df)

        # Count symbols
        symbol_counts = pd.read_sql("SELECT symbol, COUNT(*) as count FROM historical_deals GROUP BY symbol", conn)
        print("\n📊 Symbol distribution in deals:")
        print(symbol_counts)

        # Check for blank symbols
        blank_check = pd.read_sql("SELECT COUNT(*) as count FROM historical_deals WHERE symbol IS NULL OR symbol = '' OR symbol = 'nan'", conn)
        print(f"\n⚠️  Blank symbols: {blank_check['count'].iloc[0]}")
else:
    print("📊 Checking ea_trades table:")

    # Get sample trades
    trades_df = pd.read_sql("SELECT ticket, symbol, entry_time, entry_price, volume FROM ea_trades LIMIT 10", conn)
    print(trades_df)

    # Count symbols
    symbol_counts = pd.read_sql("SELECT symbol, COUNT(*) as count FROM ea_trades GROUP BY symbol", conn)
    print("\n📊 Symbol distribution:")
    print(symbol_counts)

    # Check for blank symbols
    blank_check = pd.read_sql("SELECT COUNT(*) as count FROM ea_trades WHERE symbol IS NULL OR symbol = '' OR symbol = 'nan'", conn)
    print(f"\n⚠️  Blank symbols: {blank_check['count'].iloc[0]}")

conn.close()
