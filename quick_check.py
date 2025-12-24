#!/usr/bin/env python3
"""
Quick check - What hours did the bot run and were they tradeable?
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'trading_bot'))

from datetime import datetime, timedelta
from trading_bot.config.strategy_config import (
    MEAN_REVERSION_HOURS,
    BREAKOUT_HOURS,
    BROKER_GMT_OFFSET
)

# Bot started at 14:24:34 according to log
# Let's check what hours it would have checked

print("\n" + "=" * 80)
print("🔍 QUICK DIAGNOSTIC - Why Zero Signals?")
print("=" * 80)

print(f"\n📊 Configuration:")
print(f"   BROKER_GMT_OFFSET: {BROKER_GMT_OFFSET}")
print(f"   Mean Reversion Hours (GMT): {MEAN_REVERSION_HOURS}")
print(f"   Breakout Hours (GMT): {BREAKOUT_HOURS}")

print(f"\n⏰ Bot Runtime Analysis:")
print(f"   Started: 2025-12-23 14:24:34 (your local time)")

# If bot is on Eastern Time (UTC-5), convert to GMT
# 14:24 EST = 19:24 GMT
start_hour_gmt = 19  # Assuming Eastern Time

print(f"   Start hour GMT: {start_hour_gmt}:00")
print(f"   Ran all night = checking hours: {start_hour_gmt} through next morning")

# Check which hours overnight are tradeable
tradeable_hours = sorted(set(MEAN_REVERSION_HOURS + BREAKOUT_HOURS))
print(f"\n✅ Tradeable Hours (GMT): {tradeable_hours}")

# Simulate overnight hours
overnight_hours = []
for i in range(24):
    hour = (start_hour_gmt + i) % 24
    overnight_hours.append(hour)
    if i >= 18:  # Stop after 18 hours (next morning)
        break

print(f"\n🌙 Hours Bot Would Check (first 18 hours):")
for i, hour in enumerate(overnight_hours[:18]):
    is_tradeable = hour in tradeable_hours
    status = "✅ TRADEABLE" if is_tradeable else "❌ NOT TRADEABLE"

    # Show what strategy can trade
    can_mr = hour in MEAN_REVERSION_HOURS
    can_bo = hour in BREAKOUT_HOURS

    strategies = []
    if can_mr:
        strategies.append("MR")
    if can_bo:
        strategies.append("BO")

    strat_text = f" ({', '.join(strategies)})" if strategies else ""

    print(f"   Hour {hour:02d}:00 GMT → {status}{strat_text}")

# Count tradeable hours
tradeable_count = sum(1 for h in overnight_hours[:18] if h in tradeable_hours)
print(f"\n📈 Summary:")
print(f"   Tradeable hours in first 18h: {tradeable_count}/18")
print(f"   Non-tradeable hours: {18 - tradeable_count}/18")

if tradeable_count < 3:
    print(f"\n⚠️  WARNING: Bot ran mostly during non-tradeable hours!")
    print(f"   This explains zero signals.")
    print(f"\n💡 Solutions:")
    print(f"   1. Use --test-mode to trade all hours (for testing)")
    print(f"   2. Run bot during GMT hours: {tradeable_hours}")
    print(f"   3. Change trading hours in strategy_config.py")

print(f"\n🔍 Next Step:")
print(f"   Run: python diagnose_signals.py")
print(f"   This will show if ANY confluence existed in the market")
print()
