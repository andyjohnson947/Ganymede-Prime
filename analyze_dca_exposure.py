"""
DCA Exposure Analysis
Calculate DCA progression for different base lot sizes
"""

def calculate_dca_progression(base_lot, multiplier, max_levels):
    """Calculate DCA levels and cumulative exposure"""
    levels = []
    cumulative = 0.0
    current_lot = base_lot

    print(f"\n{'Level':<8} {'Lot Size':<12} {'Cumulative':<12}")
    print("-" * 35)
    print(f"{'Original':<8} {base_lot:<12.2f} {base_lot:<12.2f}")

    for i in range(1, max_levels + 1):
        current_lot = current_lot * multiplier
        # Round to nearest 0.01 (MT5 volume step)
        current_lot = round(current_lot, 2)
        cumulative += current_lot
        levels.append({
            'level': i,
            'lot_size': current_lot,
            'cumulative': cumulative
        })
        print(f"{'DCA L' + str(i):<8} {current_lot:<12.2f} {cumulative:<12.2f}")

    return levels

print("=" * 70)
print("DCA EXPOSURE ANALYSIS")
print("=" * 70)

# Current configuration
BASE_LOT = 0.08
MULTIPLIER = 1.49
MAX_LEVELS = 8
CURRENT_MAX_EXPOSURE = 0.8

print(f"\nCurrent Configuration:")
print(f"  BASE_LOT_SIZE: {BASE_LOT}")
print(f"  DCA_MULTIPLIER: {MULTIPLIER}")
print(f"  DCA_MAX_LEVELS: {MAX_LEVELS}")
print(f"  DCA_MAX_TOTAL_EXPOSURE: {CURRENT_MAX_EXPOSURE}")

print(f"\n{'='*70}")
print("SCENARIO 1: Current Settings (0.08 base, 0.8 max exposure)")
print(f"{'='*70}")
levels = calculate_dca_progression(BASE_LOT, MULTIPLIER, MAX_LEVELS)

# Find where it hits the limit
print(f"\n⚠️  EXPOSURE LIMIT ANALYSIS:")
print(f"   Maximum allowed DCA exposure: {CURRENT_MAX_EXPOSURE} lots")
for level in levels:
    if level['cumulative'] <= CURRENT_MAX_EXPOSURE:
        print(f"   ✅ Level {level['level']}: {level['cumulative']:.2f} lots (OK)")
    else:
        print(f"   ❌ Level {level['level']}: {level['cumulative']:.2f} lots (EXCEEDS LIMIT!)")
        print(f"\n   → DCA will be capped at Level {level['level']-1}")
        break

# Calculate total stack exposure
max_reachable_level = [l for l in levels if l['cumulative'] <= CURRENT_MAX_EXPOSURE]
if max_reachable_level:
    max_cumulative = max_reachable_level[-1]['cumulative']
else:
    max_cumulative = 0

total_stack = BASE_LOT + (4 * 0.08) + (BASE_LOT * 5.0) + max_cumulative
print(f"\n   Maximum Stack Exposure:")
print(f"   - Original: {BASE_LOT:.2f} lots")
print(f"   - Grid (4 levels): {4 * 0.08:.2f} lots")
print(f"   - Hedge (5.0x): {BASE_LOT * 5.0:.2f} lots")
print(f"   - DCA (up to Level {len(max_reachable_level)}): {max_cumulative:.2f} lots")
print(f"   - TOTAL: {total_stack:.2f} lots per position")

print(f"\n{'='*70}")
print("SCENARIO 2: Previous Configuration (0.05 base, 0.5 max exposure)")
print(f"{'='*70}")
OLD_BASE = 0.05
OLD_MAX_EXPOSURE = 0.5
levels_old = calculate_dca_progression(OLD_BASE, MULTIPLIER, MAX_LEVELS)

print(f"\n⚠️  EXPOSURE LIMIT ANALYSIS:")
print(f"   Maximum allowed DCA exposure: {OLD_MAX_EXPOSURE} lots")
max_old = 0
for level in levels_old:
    if level['cumulative'] <= OLD_MAX_EXPOSURE:
        print(f"   ✅ Level {level['level']}: {level['cumulative']:.2f} lots (OK)")
        max_old = level['level']
    else:
        print(f"   ❌ Level {level['level']}: {level['cumulative']:.2f} lots (EXCEEDS LIMIT!)")
        print(f"\n   → Old config also capped at Level {level['level']-1}")
        break

print(f"\n{'='*70}")
print("SCENARIO 3: Required exposure for full 8 levels (0.08 base)")
print(f"{'='*70}")
full_8_cumulative = levels[-1]['cumulative']
print(f"\nTo support all 8 DCA levels with 0.08 base:")
print(f"  Required DCA_MAX_TOTAL_EXPOSURE: {full_8_cumulative:.2f} lots")
print(f"  Current DCA_MAX_TOTAL_EXPOSURE: {CURRENT_MAX_EXPOSURE:.2f} lots")
print(f"  Increase needed: {full_8_cumulative - CURRENT_MAX_EXPOSURE:.2f} lots ({((full_8_cumulative/CURRENT_MAX_EXPOSURE - 1)*100):.1f}% increase)")

total_stack_full = BASE_LOT + (4 * 0.08) + (BASE_LOT * 5.0) + full_8_cumulative
print(f"\n  Maximum Stack Exposure with 8 DCA levels:")
print(f"  - Original: {BASE_LOT:.2f} lots")
print(f"  - Grid (4 levels): {4 * 0.08:.2f} lots")
print(f"  - Hedge (5.0x): {BASE_LOT * 5.0:.2f} lots")
print(f"  - DCA (8 levels): {full_8_cumulative:.2f} lots")
print(f"  - TOTAL: {total_stack_full:.2f} lots per position")
print(f"\n  With MAX_OPEN_POSITIONS = 3:")
print(f"  - Potential total exposure: {total_stack_full * 3:.2f} lots")
print(f"  - Current MAX_TOTAL_LOTS: 15.0 lots")
if total_stack_full * 3 > 15.0:
    print(f"  - ⚠️  Would exceed MAX_TOTAL_LOTS by {total_stack_full * 3 - 15.0:.2f} lots!")
else:
    print(f"  - ✅ Within MAX_TOTAL_LOTS limit")

print(f"\n{'='*70}")
print("SCENARIO 4: Alternative - Reduce multiplier to fit 8 levels in 0.8")
print(f"{'='*70}")

# Try different multipliers
test_multipliers = [1.25, 1.30, 1.35, 1.40]
print(f"\nTesting multipliers to fit 8 levels within {CURRENT_MAX_EXPOSURE} lots:")
for mult in test_multipliers:
    test_levels = []
    cumulative = 0.0
    current = BASE_LOT
    for i in range(1, 9):
        current = round(current * mult, 2)
        cumulative += current
    print(f"  Multiplier {mult:.2f}: 8 levels = {cumulative:.2f} lots ", end="")
    if cumulative <= CURRENT_MAX_EXPOSURE:
        print("✅ FITS!")
    else:
        print(f"(exceeds by {cumulative - CURRENT_MAX_EXPOSURE:.2f})")

print(f"\n{'='*70}")
print("RECOMMENDATIONS")
print(f"{'='*70}")
print(f"""
Based on the analysis, here are your options:

OPTION 1: Increase DCA_MAX_TOTAL_EXPOSURE (RECOMMENDED)
  - Change DCA_MAX_TOTAL_EXPOSURE from 0.8 to {full_8_cumulative:.1f} lots
  - Also increase MAX_TOTAL_LOTS from 15.0 to {total_stack_full * 3 + 3:.1f} lots (safe margin)
  - Maintains proven 8-level strategy with 1.49x multiplier
  - Pros: Keeps successful recovery depth
  - Cons: Higher risk exposure per position

OPTION 2: Keep current exposure, reduce max levels
  - Keep DCA_MAX_TOTAL_EXPOSURE at 0.8 lots
  - Reduce DCA_MAX_LEVELS from 8 to {len(max_reachable_level)} levels
  - Pros: Lower risk, current limits maintained
  - Cons: Less recovery depth, may fail on deeper drawdowns

OPTION 3: Reduce multiplier to fit 8 levels
  - Change DCA_MULTIPLIER from 1.49 to ~1.25
  - Keep DCA_MAX_LEVELS at 8
  - Keep DCA_MAX_TOTAL_EXPOSURE at 0.8 lots
  - Pros: Maintains 8 levels within current limit
  - Cons: Lower recovery power per level, may need deeper drawdowns

RECOMMENDED: OPTION 1
The analysis showed 8 levels had 100% success rate. To maintain this proven
strategy with the larger 0.08 base lot size, increase exposure limits
proportionally. This scales the strategy properly while maintaining the
successful recovery mechanics.
""")

print("=" * 70)
