#!/usr/bin/env python3
"""
Signal Diagnostic Tool
Check why signals are not being generated
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'trading_bot'))

from config.strategy_config import (
    MIN_CONFLUENCE_SCORE,
    TREND_FILTER_ENABLED,
    ADX_THRESHOLD,
    ADX_STRONG_THRESHOLD,
    ALLOW_WEAK_TRENDS,
    CONFLUENCE_WEIGHTS,
    SYMBOLS
)

print("=" * 80)
print("SIGNAL GENERATION DIAGNOSTIC")
print("=" * 80)

print("\n📊 Current Signal Requirements:")
print(f"   • Minimum confluence score: {MIN_CONFLUENCE_SCORE}")
print(f"   • Trend filter enabled: {TREND_FILTER_ENABLED}")
print(f"   • ADX threshold: {ADX_THRESHOLD}")
print(f"   • Allow weak trends: {ALLOW_WEAK_TRENDS}")
print(f"   • Skip strong trends (ADX > {ADX_STRONG_THRESHOLD}): True")

print("\n🎯 Confluence Weights:")
print("   H1 Factors (weight 1):")
print("     - VWAP Band 1 or Band 2: 1 point each")
print("     - POC / VAH / VAL / LVN: 1 point each")
print("     - Swing high/low: 1 point each")
print("\n   HTF Factors (weight 2-3):")
for factor, weight in CONFLUENCE_WEIGHTS.items():
    if weight > 1:
        print(f"     - {factor}: {weight} points")

print("\n⚠️  Common Signal Blockers:")
print("\n1. TREND FILTER BLOCKING (Most Common)")
print(f"   • If ADX > {ADX_THRESHOLD}: Signal blocked (unless weak trend)")
print(f"   • If ADX > {ADX_STRONG_THRESHOLD}: Always blocked")
print("   • Solution: Market must be ranging (ADX < 25)")

print("\n2. INSUFFICIENT CONFLUENCE")
print(f"   • Need {MIN_CONFLUENCE_SCORE}+ points to trigger")
print("   • Example valid signal:")
print("     - VWAP Band 2 (1) + POC (1) + Prev Day VAH (2) = 4 ✅")
print("   • Example invalid:")
print("     - VWAP Band 1 (1) + Below VAL (1) = 2 ❌")

print("\n3. NO VWAP BAND TOUCH")
print("   • Price must be at VWAP ±1σ or ±2σ")
print("   • If price near VWAP center, no primary signal")

print("\n4. WRONG MARKET CONDITIONS")
print("   • EA performs best in ranging markets")
print("   • Strong trends = no signals (by design)")

print("\n" + "=" * 80)
print("💡 TROUBLESHOOTING STEPS")
print("=" * 80)

print("\n**Option 1: Lower Confluence Requirement (Cautious)**")
print("   Edit: trading_bot/config/strategy_config.py")
print("   Change: MIN_CONFLUENCE_SCORE = 4")
print("   To:     MIN_CONFLUENCE_SCORE = 3")
print("   ⚠️  Warning: May reduce win rate")

print("\n**Option 2: Disable Trend Filter (Risky)**")
print("   Edit: trading_bot/config/strategy_config.py")
print("   Change: TREND_FILTER_ENABLED = True")
print("   To:     TREND_FILTER_ENABLED = False")
print("   ⚠️  WARNING: Will trade in trends (dangerous!)")

print("\n**Option 3: Relax Trend Threshold (Moderate)**")
print("   Edit: trading_bot/config/strategy_config.py")
print("   Change: ADX_THRESHOLD = 25")
print("   To:     ADX_THRESHOLD = 30")
print("   ✅ Allows more signals while keeping some protection")

print("\n**Option 4: Check Logs (Recommended)**")
print("   • Check: logs/signals.log")
print("   • Look for: Rejected signals with reasons")
print("   • Shows: What's actually blocking")

print("\n**Option 5: Add Debug Logging**")
print("   • Shows confluence scores even when < 4")
print("   • Shows ADX values and trend filter decisions")
print("   • Helps identify exact blocker")

print("\n" + "=" * 80)
print("🔍 RECOMMENDED ACTIONS")
print("=" * 80)

print("\n1. **Check current market conditions:**")
print("   • Is the market trending or ranging?")
print("   • Check ADX value on your charts")
print("   • ADX < 25 = ranging (good for signals)")
print("   • ADX > 25 = trending (signals blocked)")

print("\n2. **Monitor for a few hours:**")
print("   • Signals require specific confluence")
print("   • May not happen every minute/hour")
print("   • EA averaged specific entry patterns")

print("\n3. **Check symbol configuration:**")
print(f"   • Configured symbols: {SYMBOLS if SYMBOLS else 'None configured!'}")
print("   • Make sure you're trading the right symbols")

print("\n4. **Enable verbose logging:**")
print("   • See what confluence scores are being calculated")
print("   • Identify which factor is missing")

print("\n" + "=" * 80)
print("Would you like me to:")
print("  1. Lower confluence to 3 (more signals, lower quality)?")
print("  2. Relax ADX threshold to 30 (allow mild trends)?")
print("  3. Add debug logging to see rejected signals?")
print("  4. Check what symbols are configured?")
print("=" * 80)
