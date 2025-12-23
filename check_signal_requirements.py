"""
Check what conditions are needed for signals right now
"""
import sys
from datetime import datetime

sys.path.insert(0, 'trading_bot')

from strategies.time_filters import TimeFilter
from config import strategy_config as cfg

# Current time
now = datetime.utcnow()
print("=" * 80)
print("SIGNAL DETECTION REQUIREMENTS")
print("=" * 80)
print(f"\nCurrent Time: {now.strftime('%Y-%m-%d %H:%M:%S')} GMT")
print(f"Day: {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][now.weekday()]}")
print(f"Hour: {now.hour}:00 GMT")

# Check time filters
tf = TimeFilter()
can_mr = tf.can_trade_mean_reversion(now)
can_bo = tf.can_trade_breakout(now)

print("\n" + "=" * 80)
print("TIME FILTER STATUS")
print("=" * 80)

print(f"\n✅ MEAN REVERSION: {'ACTIVE' if can_mr else 'INACTIVE'}")
if can_mr:
    print("   Can trade mean reversion signals now")
    print("\n   Mean Reversion Signal Requirements:")
    print("   1. Price at VWAP ±1σ or ±2σ bands")
    print("   2. OR price at POC (Point of Control)")
    print("   3. OR price at Value Area High/Low (VAH/VAL)")
    print("   4. Confluence score ≥ 4 factors aligned")
    print("   5. ADX shows ranging market (not strong trend)")
    print("   6. Not during strong directional move")
    print("\n   📊 This requires:")
    print("      - Price precisely at key levels")
    print("      - Multiple factors confirming")
    print("      - Market in consolidation")
else:
    print(f"   ❌ Hour {now.hour} not in mean reversion hours: {cfg.MEAN_REVERSION_HOURS}")
    print(f"   Next MR windows: 05:00, 06:00, 07:00, 09:00, 12:00 GMT")

print(f"\n{'✅' if can_bo else '❌'} BREAKOUT: {'ACTIVE' if can_bo else 'INACTIVE'}")
if can_bo:
    print("   Can trade breakout signals now")
    print("\n   Breakout Signal Requirements:")
    print("   1. Price breaks recent range high/low (20 bar lookback)")
    print("   2. Volume spike: 1.5x average volume")
    print("   3. ATR elevated: 1.2x median (increased volatility)")
    print("   4. Candle closes beyond breakout level (not just wick)")
    print("   5. Range size minimum: 20 pips")
    print("   6. RSI confirmation (>60 for buy, <40 for sell)")
    print("\n   📊 This requires:")
    print("      - Clear consolidation range forming")
    print("      - Strong breakout with volume")
    print("      - Momentum confirmation")
else:
    print(f"   ❌ Hour {now.hour} not in breakout hours: {cfg.BREAKOUT_HOURS}")
    print(f"   Next BO windows: 03:00, 14:00-16:00 GMT")

print("\n" + "=" * 80)
print("WHY YOU MIGHT NOT SEE SIGNALS")
print("=" * 80)

print("\n🎯 SIGNAL SELECTIVITY IS INTENTIONAL:")
print("   - 64.3% win rate = very selective strategy")
print("   - Historical: ~413 trades over extended period")
print("   - Only trades high-probability setups")
print("   - May go hours without a signal")

print("\n📊 CURRENT MARKET MUST MEET SPECIFIC CONDITIONS:")
if can_bo:
    print("   For breakout (active now):")
    print("   ❌ Is EURUSD/GBPUSD forming a tight range?")
    print("   ❌ Is volume spiking above 1.5x average?")
    print("   ❌ Is ATR showing increased volatility?")
    print("   ❌ Is price breaking and closing beyond range?")
    print("\n   If ANY of these are NO → No signal")
    
if can_mr:
    print("   For mean reversion (active now):")
    print("   ❌ Is price exactly at VWAP bands?")
    print("   ❌ Is price at POC or Value Area?")
    print("   ❌ Are 4+ factors aligned?")
    print("   ❌ Is market ranging (not trending)?")
    print("\n   If ANY of these are NO → No signal")

print("\n" + "=" * 80)
print("HOW TO VERIFY BOT IS WORKING")
print("=" * 80)

print("\n✅ Check logs for activity:")
print("   tail -f trading_bot/trading_bot.log")
print("\n   You should see:")
print("   - 'Refreshing market data for EURUSD'")
print("   - 'Checking signals for EURUSD/GBPUSD'")
print("   - No errors or crashes")

print("\n✅ Bot is working correctly if:")
print("   - Process is running")
print("   - Logs show regular checks (every minute)")
print("   - No errors in output")
print("   - MT5 connected")

print("\n❌ Bot has a problem if:")
print("   - No log activity")
print("   - Error messages appearing")
print("   - MT5 connection errors")
print("   - Process crashes")

print("\n" + "=" * 80)
print("PATIENCE IS KEY")
print("=" * 80)
print("\n💡 The bot's selectivity is its strength!")
print("   - Waits for perfect setups")
print("   - Avoids low-probability trades")
print("   - Higher win rate but fewer trades")
print("\n   This is GOOD - don't force trades!")

print("\n" + "=" * 80)
