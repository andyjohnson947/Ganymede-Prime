#!/usr/bin/env python3
"""
Diagnose Drawdown Calculation Bug
Shows exactly what MT5 returns for account info and positions
"""

import MetaTrader5 as mt5
import sys

if len(sys.argv) < 4:
    print("Usage: python diagnose_drawdown.py <login> <password> <server>")
    sys.exit(1)

login = int(sys.argv[1])
password = sys.argv[2]
server = sys.argv[3]

# Connect
if not mt5.initialize():
    print("Failed to initialize MT5")
    sys.exit(1)

if not mt5.login(login, password=password, server=server):
    print(f"Failed to login: {mt5.last_error()}")
    mt5.shutdown()
    sys.exit(1)

print("="*80)
print("MT5 ACCOUNT DIAGNOSTICS")
print("="*80)

# Get account info
account = mt5.account_info()
if account:
    print(f"\n📊 Account Info:")
    print(f"   Login: {account.login}")
    print(f"   Server: {account.server}")
    print(f"   Balance: ${account.balance:.2f}")
    print(f"   Equity: ${account.equity:.2f}")
    print(f"   Margin: ${account.margin:.2f}")
    print(f"   Free Margin: ${account.margin_free:.2f}")
    print(f"   Margin Level: {account.margin_level:.2f}%")
    print(f"   Profit: ${account.profit:.2f}")

    # Calculate actual drawdown
    if account.balance > 0:
        actual_dd = ((account.balance - account.equity) / account.balance) * 100
        print(f"\n💡 Actual Unrealized Loss:")
        print(f"   Balance: ${account.balance:.2f}")
        print(f"   Equity: ${account.equity:.2f}")
        print(f"   Unrealized Loss: ${account.balance - account.equity:.2f}")
        print(f"   Percent: {actual_dd:.2f}%")
else:
    print("❌ Failed to get account info")

# Get positions
positions = mt5.positions_get()
if positions:
    print(f"\n📈 Open Positions: {len(positions)}")
    total_profit = 0
    for pos in positions:
        total_profit += pos.profit
        print(f"\n   Ticket: {pos.ticket}")
        print(f"   Symbol: {pos.symbol}")
        print(f"   Type: {'BUY' if pos.type == 0 else 'SELL'}")
        print(f"   Volume: {pos.volume}")
        print(f"   Entry: {pos.price_open:.5f}")
        print(f"   Current: {pos.price_current:.5f}")
        print(f"   Profit: ${pos.profit:.2f}")
        print(f"   Swap: ${pos.swap:.2f}")
        if hasattr(pos, 'commission'):
            print(f"   Commission: ${pos.commission:.2f}")

    print(f"\n   Total Unrealized P&L: ${total_profit:.2f}")
else:
    print("\n📊 No open positions")

# Get closed trades (last 10)
from datetime import datetime, timedelta
history_start = datetime.now() - timedelta(days=7)
deals = mt5.history_deals_get(history_start, datetime.now())

if deals:
    print(f"\n📜 Recent Closed Trades (last 10):")
    closed_pl = 0
    for deal in list(deals)[-10:]:
        if deal.entry == 1:  # Exit deals only
            closed_pl += deal.profit
            print(f"   {deal.time} | {deal.symbol} | ${deal.profit:.2f}")
    print(f"\n   Total Realized P&L (last 10): ${closed_pl:.2f}")

print("\n" + "="*80)
print("DIAGNOSIS:")
print("="*80)

if account:
    if account.equity < account.balance:
        loss = account.balance - account.equity
        print(f"⚠️  You have ${loss:.2f} in unrealized losses from open positions")
        print(f"   This is being counted as {((loss / account.balance) * 100):.2f}% drawdown")
        print(f"   If you close all positions at current prices, your balance will be ${account.equity:.2f}")
    elif account.equity > account.balance:
        profit = account.equity - account.balance
        print(f"✅ You have ${profit:.2f} in unrealized profits from open positions")
    else:
        print(f"✅ No open positions or unrealized P&L = $0")

    print(f"\n💡 For drawdown calculation:")
    print(f"   Peak Balance (when bot started): Should be ${account.equity:.2f}")
    print(f"   Current Equity: ${account.equity:.2f}")
    print(f"   Drawdown from CURRENT equity: Should be 0%")

    if account.equity < account.balance:
        print(f"\n🔧 FIX: The bot should use CURRENT EQUITY as initial peak when it starts!")
        print(f"   Not balance: ${account.balance:.2f}")
        print(f"   But equity: ${account.equity:.2f}")

mt5.shutdown()
