#!/usr/bin/env python3
"""
Emergency fix script - patches reverse_engineer_ea.py to use safe field access
Run this on Windows if git sync isn't working
"""

import re
import shutil
from pathlib import Path

def fix_file():
    file_path = Path("reverse_engineer_ea.py")

    if not file_path.exists():
        print(f"❌ Error: {file_path} not found!")
        print("Make sure you run this from the EA-Analysis directory")
        return False

    # Backup original
    backup_path = file_path.with_suffix('.py.backup')
    shutil.copy2(file_path, backup_path)
    print(f"✓ Created backup: {backup_path}")

    # Read content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Fix all trade field access patterns
    replacements = [
        (r"trade\['entry_time'\]", "trade.get('entry_time')"),
        (r"trade\['entry_price'\]", "trade.get('entry_price', 0)"),
        (r"trade\['trade_type'\]", "trade.get('trade_type', 'unknown')"),
        (r"trade\['volume'\]", "trade.get('volume', 0)"),
        (r"trade\['type'\]", "trade.get('type', 'unknown')"),
        (r"trade\['symbol'\]", "trade.get('symbol', '')"),
        (r"trade\['profit'\]", "trade.get('profit', 0)"),
        (r"trade\['exit_time'\]", "trade.get('exit_time')"),
        (r"trade\['exit_price'\]", "trade.get('exit_price')"),
        (r"prev_trade\['entry_time'\]", "prev_trade.get('entry_time')"),
        (r"prev_trade\['trade_type'\]", "prev_trade.get('trade_type', 'unknown')"),
        (r"current_group\[-1\]\['trade_type'\]", "current_group[-1].get('trade_type', 'unknown')"),
        (r"current_sequence\[0\]\['trade_type'\]", "current_sequence[0].get('trade_type', 'unknown')"),
        (r"trade1\['volume'\]", "trade1.get('volume', 0)"),
        (r"trade1\['trade_type'\]", "trade1.get('trade_type', 'unknown')"),
        (r"trade1\['entry_price'\]", "trade1.get('entry_price', 0)"),
        (r"trade1\['entry_time'\]", "trade1.get('entry_time')"),
    ]

    changes_made = 0
    for pattern, replacement in replacements:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            matches = len(re.findall(pattern, content))
            changes_made += matches
            print(f"✓ Fixed {matches} instance(s) of: {pattern}")
            content = new_content

    if changes_made == 0:
        print("✓ No changes needed - file is already up to date!")
        return True

    # Write fixed content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\n✅ Successfully applied {changes_made} fixes to {file_path}")
    print(f"   Backup saved as: {backup_path}")
    print("\n🚀 You can now run: python EASY_START.py")

    return True

if __name__ == "__main__":
    print("="*70)
    print("  EA ANALYSIS - EMERGENCY FIX SCRIPT")
    print("="*70)
    print("\nThis will fix all trade field access errors in reverse_engineer_ea.py\n")

    success = fix_file()

    if not success:
        input("\nPress Enter to exit...")
        exit(1)

    input("\nPress Enter to exit...")
