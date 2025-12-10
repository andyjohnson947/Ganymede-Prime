"""
MT5 History Diagnostic Script
Checks what the MT5 API can actually see
"""

import MetaTrader5 as mt5
from datetime import datetime

print("=" * 70)
print("  MT5 HISTORY DIAGNOSTIC")
print("=" * 70)

# Initialize
if not mt5.initialize():
    print("ERROR: Could not initialize MT5")
    print(f"Error: {mt5.last_error()}")
    exit(1)

print("\n✓ Connected to MT5")

# Get account info
account = mt5.account_info()
if account:
    print(f"\nAccount: {account.login}")
    print(f"Server: {account.server}")
    print(f"Balance: ${account.balance:,.2f}")
    print(f"Currency: {account.currency}")
    print(f"Leverage: 1:{account.leverage}")
else:
    print("\nERROR: Could not get account info")
    mt5.shutdown()
    exit(1)

print("\n" + "-" * 70)
print("CHECKING HISTORY ACCESS...")
print("-" * 70)

# Try different date ranges
test_dates = [
    ("Last 90 days", datetime(2024, 9, 1), datetime.now()),
    ("Last year", datetime(2024, 1, 1), datetime.now()),
    ("Since 2023", datetime(2023, 1, 1), datetime.now()),
    ("Since 2020", datetime(2020, 1, 1), datetime.now()),
    ("All time", datetime(1970, 1, 1), datetime.now()),
]

for label, start, end in test_dates:
    print(f"\n{label} ({start.date()} to {end.date()}):")

    # Check deals
    deals = mt5.history_deals_get(start, end)
    if deals is None:
        print(f"  Deals: None (error: {mt5.last_error()})")
    else:
        print(f"  Deals: {len(deals)}")

    # Check orders
    orders = mt5.history_orders_get(start, end)
    if orders is None:
        print(f"  Orders: None (error: {mt5.last_error()})")
    else:
        print(f"  Orders: {len(orders)}")

print("\n" + "-" * 70)
print("CHECKING CURRENT POSITIONS...")
print("-" * 70)

# Check open positions
positions = mt5.positions_get()
if positions is None:
    print(f"ERROR getting positions: {mt5.last_error()}")
else:
    print(f"\nOpen positions: {len(positions)}")
    if len(positions) > 0:
        print("\nOpen positions details:")
        for pos in positions[:5]:  # Show first 5
            print(f"  - {pos.symbol} {pos.type} {pos.volume} lots, Profit: ${pos.profit:.2f}")

print("\n" + "-" * 70)
print("CHECKING HISTORY TOTAL...")
print("-" * 70)

# Try to get total history
total_deals = mt5.history_deals_total(datetime(1970, 1, 1), datetime.now())
total_orders = mt5.history_orders_total(datetime(1970, 1, 1), datetime.now())

print(f"\nTotal deals in history: {total_deals}")
print(f"Total orders in history: {total_orders}")

if total_deals > 0:
    print("\n✓ History exists! Trying to fetch...")
    deals = mt5.history_deals_get(datetime(1970, 1, 1), datetime.now())
    if deals:
        print(f"✓ Successfully fetched {len(deals)} deals")
        print("\nFirst few deals:")
        for deal in deals[:3]:
            print(f"  - Ticket: {deal.ticket}, Symbol: {deal.symbol}, "
                  f"Type: {deal.type}, Volume: {deal.volume}, "
                  f"Profit: ${deal.profit:.2f}, Time: {datetime.fromtimestamp(deal.time)}")
    else:
        print(f"✗ Could not fetch deals. Error: {mt5.last_error()}")

print("\n" + "-" * 70)
print("TERMINAL INFO...")
print("-" * 70)

terminal = mt5.terminal_info()
if terminal:
    print(f"\nTerminal path: {terminal.path}")
    print(f"Data path: {terminal.data_path}")
    print(f"Community account: {terminal.community_account}")
    print(f"Connected: {terminal.connected}")
    print(f"Trade allowed: {terminal.trade_allowed}")

print("\n" + "=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)

mt5.shutdown()

input("\nPress Enter to exit...")
