"""
Quick script to check which symbols are available from your broker
Run this to verify symbol names before adding to SYMBOLS config
"""

import MetaTrader5 as mt5
from datetime import datetime

# Initialize MT5
if not mt5.initialize():
    print("❌ Failed to initialize MT5")
    print(f"   Error: {mt5.last_error()}")
    exit()

print("✅ MT5 Connected\n")

# Symbols to check
symbols_to_check = [
    'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD', 'AUDUSD', 'NZDUSD',
    'EURCHF', 'EURGBP', 'EURJPY', 'GBPJPY', 'AUDNZD', 'AUDCAD',
    'EUR/CHF', 'AUD/NZD',  # Check if broker uses slashes
]

print("🔍 Checking symbol availability...\n")

available = []
unavailable = []

for symbol in symbols_to_check:
    # Try to get symbol info
    info = mt5.symbol_info(symbol)

    if info is None:
        unavailable.append(symbol)
        continue

    # Try to select symbol for trading
    if not mt5.symbol_select(symbol, True):
        unavailable.append(symbol)
        continue

    # Try to get a tick
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        unavailable.append(symbol)
        continue

    # Try to get historical data
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 10)
    if rates is None or len(rates) == 0:
        print(f"⚠️  {symbol}: Available but no H1 data (market closed or no history)")
        unavailable.append(symbol)
        continue

    # Symbol is fully available
    available.append(symbol)
    print(f"✅ {symbol}: Available (bid: {tick.bid:.5f}, ask: {tick.ask:.5f})")

print(f"\n{'='*60}")
print(f"✅ Available symbols: {len(available)}")
for sym in available:
    print(f"   - {sym}")

print(f"\n❌ Unavailable symbols: {len(unavailable)}")
for sym in unavailable:
    print(f"   - {sym}")

print(f"\n{'='*60}")
print("\nTo use these symbols, add them to trading_bot/config/strategy_config.py:")
print(f"SYMBOLS = {available[:5]}")  # Show first 5 as example

# Get all available symbols from broker
print(f"\n{'='*60}")
print("📋 All symbols available from your broker:")
all_symbols = mt5.symbols_get()
if all_symbols:
    # Filter for common forex pairs
    forex_symbols = [s.name for s in all_symbols if any(curr in s.name for curr in ['USD', 'EUR', 'GBP', 'JPY', 'AUD', 'NZD', 'CAD', 'CHF'])]

    print(f"\nForex pairs ({len(forex_symbols)} found):")
    for sym in sorted(forex_symbols)[:50]:  # Show first 50
        print(f"   - {sym}")

mt5.shutdown()
