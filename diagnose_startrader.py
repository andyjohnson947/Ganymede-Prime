#!/usr/bin/env python3
"""
StarTrader Account Diagnostic Tool
Checks account permissions, symbol status, and trading settings
"""

import MetaTrader5 as mt5
import sys


def diagnose_startrader_account(login: int, password: str, server: str):
    """
    Diagnose StarTrader account and identify trading issues

    Args:
        login: MT5 account number
        password: Account password
        server: Server name
    """

    print("=" * 80)
    print("STARTRADER ACCOUNT DIAGNOSTIC")
    print("=" * 80)
    print()

    # Initialize MT5
    if not mt5.initialize():
        print("❌ Failed to initialize MT5")
        print(f"   Error: {mt5.last_error()}")
        return

    # Login to account
    print(f"🔐 Logging in to {server}...")
    authorized = mt5.login(login, password=password, server=server)

    if not authorized:
        print("❌ Login failed")
        error = mt5.last_error()
        print(f"   Error code: {error[0]}")
        print(f"   Error message: {error[1]}")
        mt5.shutdown()
        return

    print("✅ Login successful")
    print()

    # Account Information
    print("=" * 80)
    print("ACCOUNT INFORMATION")
    print("=" * 80)
    print()

    account_info = mt5.account_info()
    if account_info is None:
        print("❌ Failed to get account info")
    else:
        print(f"Account Type: {'Demo' if account_info.trade_mode == 0 else 'Real'}")
        print(f"Balance: ${account_info.balance:.2f}")
        print(f"Equity: ${account_info.equity:.2f}")
        print(f"Margin: ${account_info.margin:.2f}")
        print(f"Free Margin: ${account_info.margin_free:.2f}")
        print(f"Leverage: 1:{account_info.leverage}")
        print(f"Currency: {account_info.currency}")
        print()

        # Check trading permissions
        print("TRADING PERMISSIONS:")
        print(f"  Trade Allowed: {'✅ YES' if account_info.trade_allowed else '❌ NO'}")
        print(f"  Trade Expert: {'✅ YES' if account_info.trade_expert else '❌ NO - ALGO TRADING DISABLED!'}")
        print()

        if not account_info.trade_expert:
            print("⚠️  ISSUE FOUND: Algo trading is disabled!")
            print("   FIX: MT5 → Tools → Options → Expert Advisors → Enable 'Allow algorithmic trading'")
            print()

    # Terminal Information
    print("=" * 80)
    print("MT5 TERMINAL SETTINGS")
    print("=" * 80)
    print()

    terminal_info = mt5.terminal_info()
    if terminal_info:
        print(f"Terminal Build: {terminal_info.build}")
        print(f"Trade Allowed: {'✅ YES' if terminal_info.trade_allowed else '❌ NO'}")
        print(f"Algo Trading Allowed: {'✅ YES' if terminal_info.tradeapi_disabled == False else '❌ NO'}")
        print(f"Email Enabled: {'✅ YES' if terminal_info.email_enabled else '❌ NO'}")
        print()

        if terminal_info.tradeapi_disabled:
            print("⚠️  ISSUE FOUND: Trade API is disabled in terminal!")
            print()

    # Check EURUSD Symbol
    print("=" * 80)
    print("SYMBOL INFORMATION (EURUSD)")
    print("=" * 80)
    print()

    # Try different symbol formats
    symbol_formats = ['EURUSD', 'EURUSD.a', 'EURUSDm', 'EURUSD-sb', 'EUR/USD']

    working_symbol = None

    for symbol_name in symbol_formats:
        symbol_info = mt5.symbol_info(symbol_name)

        if symbol_info is not None:
            print(f"✅ Found: {symbol_name}")
            working_symbol = symbol_name

            print(f"   Name: {symbol_info.name}")
            print(f"   Description: {symbol_info.description}")
            print(f"   Visible: {'✅ YES' if symbol_info.visible else '❌ NO'}")
            print(f"   Trade Mode: {symbol_info.trade_mode}")
            print(f"     0=Disabled, 1=LongOnly, 2=ShortOnly, 3=CloseOnly, 4=Full")

            if symbol_info.trade_mode == 4:
                print(f"   ✅ Full trading enabled")
            elif symbol_info.trade_mode == 0:
                print(f"   ❌ TRADING DISABLED for this symbol!")
            else:
                print(f"   ⚠️  Limited trading mode")

            print(f"   Spread: {symbol_info.spread}")
            print(f"   Digits: {symbol_info.digits}")
            print(f"   Min Volume: {symbol_info.volume_min}")
            print(f"   Max Volume: {symbol_info.volume_max}")
            print(f"   Volume Step: {symbol_info.volume_step}")
            print(f"   Bid: {symbol_info.bid}")
            print(f"   Ask: {symbol_info.ask}")

            # Filling modes
            print(f"   Filling Modes:")
            if symbol_info.filling_mode & 1:  # FOK
                print(f"     ✅ ORDER_FILLING_FOK (Fill or Kill)")
            if symbol_info.filling_mode & 2:  # IOC
                print(f"     ✅ ORDER_FILLING_IOC (Immediate or Cancel)")
            if symbol_info.filling_mode & 4:  # RETURN
                print(f"     ✅ ORDER_FILLING_RETURN")

            # Check if market is open
            print(f"   Session Trades Allowed: {symbol_info.trade_mode}")

            # Check current quote time
            tick = mt5.symbol_info_tick(symbol_name)
            if tick:
                print(f"   Last Tick Time: {tick.time}")
                print(f"   Current Bid/Ask: {tick.bid}/{tick.ask}")
            else:
                print(f"   ⚠️  No tick data - market might be closed")

            print()
            break
        else:
            print(f"❌ Not found: {symbol_name}")

    if working_symbol is None:
        print()
        print("⚠️  ISSUE FOUND: EURUSD symbol not found!")
        print("   Available symbols:")
        symbols = mt5.symbols_get()
        if symbols:
            eur_symbols = [s.name for s in symbols if 'EUR' in s.name][:10]
            for sym in eur_symbols:
                print(f"     - {sym}")
        print()

    # Test Order Creation (dry run - check what error we'd get)
    print("=" * 80)
    print("ORDER TEST (Checking for errors)")
    print("=" * 80)
    print()

    if working_symbol:
        symbol_info = mt5.symbol_info(working_symbol)

        # Create a test order request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": working_symbol,
            "volume": symbol_info.volume_min,  # Use minimum lot size
            "type": mt5.ORDER_TYPE_BUY,
            "price": symbol_info.ask,
            "deviation": 20,
            "magic": 234000,
            "comment": "StarTrader Test",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        print(f"Test order parameters:")
        print(f"  Symbol: {request['symbol']}")
        print(f"  Volume: {request['volume']}")
        print(f"  Type: BUY")
        print(f"  Price: {request['price']}")
        print()

        # Check the order (but don't actually send it)
        result = mt5.order_check(request)

        if result is None:
            print("❌ order_check() failed")
            error = mt5.last_error()
            print(f"   Error code: {error[0]}")
            print(f"   Error message: {error[1]}")
        else:
            print(f"Order Check Result:")
            print(f"  Return Code: {result.retcode}")
            print(f"  Return Message: {result.comment}")

            if result.retcode == mt5.TRADE_RETCODE_DONE or result.retcode == 0:
                print(f"  ✅ Order check passed - trading should work!")
            elif result.retcode == 10027:
                print(f"  ❌ TRADE DISABLED - Algo trading is off!")
                print(f"     FIX: Enable algo trading in MT5 settings")
            elif result.retcode == 10018:
                print(f"  ❌ MARKET CLOSED")
                print(f"     Wait for forex market to open")
            elif result.retcode == 10019:
                print(f"  ❌ NO PRICES - No quotes available")
            elif result.retcode == 10016:
                print(f"  ❌ INVALID STOPS")
            else:
                print(f"  ⚠️  Unexpected return code: {result.retcode}")

        print()

    # Summary
    print("=" * 80)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 80)
    print()

    issues = []

    if account_info and not account_info.trade_expert:
        issues.append("❌ Algo trading disabled in account settings")

    if terminal_info and terminal_info.tradeapi_disabled:
        issues.append("❌ Trade API disabled in terminal")

    if working_symbol is None:
        issues.append("❌ EURUSD symbol not found or has different name")

    if not issues:
        print("✅ No obvious issues found!")
        print()
        print("If you're still getting 'Trade disabled' error:")
        print("1. Restart MT5 terminal")
        print("2. Check if demo account has expired")
        print("3. Contact StarTrader support")
    else:
        print("Issues found:")
        for issue in issues:
            print(f"  {issue}")
        print()
        print("FIXES:")
        print("1. MT5 → Tools → Options → Expert Advisors")
        print("2. Enable 'Allow algorithmic trading'")
        print("3. Enable 'Allow DLL imports'")
        print("4. Restart MT5")

    mt5.shutdown()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python diagnose_startrader.py <login> <password> <server>")
        print()
        print("Example:")
        print("  python diagnose_startrader.py 12345 yourpass 'StarTrader-Demo'")
        sys.exit(1)

    login = int(sys.argv[1])
    password = sys.argv[2]
    server = sys.argv[3]

    diagnose_startrader_account(login, password, server)
