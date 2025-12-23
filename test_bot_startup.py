"""
Test if bot can start without MT5 connection
"""
import sys
import os

# Add to path
sys.path.insert(0, 'trading_bot')

print("=" * 80)
print("BOT STARTUP TEST")
print("=" * 80)

# Test 1: Import core modules
print("\n1. Testing imports...")
try:
    from config import strategy_config as cfg
    print("   ✅ strategy_config imported")
except Exception as e:
    print(f"   ❌ strategy_config failed: {e}")
    sys.exit(1)

try:
    from strategies.confluence_strategy import ConfluenceStrategy
    print("   ✅ ConfluenceStrategy imported")
except Exception as e:
    print(f"   ❌ ConfluenceStrategy failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    from strategies.time_filters import TimeFilter
    print("   ✅ TimeFilter imported")
except Exception as e:
    print(f"   ❌ TimeFilter failed: {e}")
    sys.exit(1)

try:
    from strategies.breakout_strategy import BreakoutStrategy
    print("   ✅ BreakoutStrategy imported")
except Exception as e:
    print(f"   ❌ BreakoutStrategy failed: {e}")
    sys.exit(1)

try:
    from strategies.partial_close_manager import PartialCloseManager
    print("   ✅ PartialCloseManager imported")
except Exception as e:
    print(f"   ❌ PartialCloseManager failed: {e}")
    sys.exit(1)

# Test 2: Check configuration
print("\n2. Checking configuration...")
print(f"   SYMBOLS: {cfg.SYMBOLS}")
if not cfg.SYMBOLS:
    print("   ❌ ERROR: SYMBOLS is empty!")
    sys.exit(1)
else:
    print(f"   ✅ Trading symbols configured: {cfg.SYMBOLS}")

print(f"   BASE_LOT_SIZE: {cfg.BASE_LOT_SIZE}")
print(f"   ENABLE_TIME_FILTERS: {cfg.ENABLE_TIME_FILTERS}")
print(f"   BREAKOUT_ENABLED: {cfg.BREAKOUT_ENABLED}")
print(f"   PARTIAL_CLOSE_ENABLED: {cfg.PARTIAL_CLOSE_ENABLED}")

# Test 3: Check MT5 availability
print("\n3. Checking MT5 module...")
try:
    import MetaTrader5 as mt5
    print("   ✅ MetaTrader5 module installed")
    print(f"   MT5 Version: {mt5.__version__ if hasattr(mt5, '__version__') else 'Unknown'}")
except ImportError as e:
    print("   ❌ MetaTrader5 module NOT installed!")
    print("   This is REQUIRED to run the bot")
    print("   Install with: pip install MetaTrader5")
    sys.exit(1)

# Test 4: Check if MT5 can initialize (without login)
print("\n4. Testing MT5 initialization...")
try:
    if mt5.initialize():
        print("   ✅ MT5 terminal detected and initialized")
        mt5.shutdown()
    else:
        print("   ⚠️  MT5 initialize failed - is MT5 terminal running?")
        print(f"   Error: {mt5.last_error()}")
        print("   You need to:")
        print("   1. Open MT5 terminal")
        print("   2. Login to your account")
        print("   3. Then start the bot")
except Exception as e:
    print(f"   ❌ MT5 error: {e}")

print("\n" + "=" * 80)
print("STARTUP TEST COMPLETE")
print("=" * 80)
print("\nIf all tests passed, you can start the bot with:")
print("python trading_bot/main.py --login YOUR_LOGIN --password YOUR_PASS --server YOUR_SERVER")
print("\n⚠️  Make sure MT5 terminal is open and logged in first!")
print("=" * 80)
