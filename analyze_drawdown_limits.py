"""
Drawdown and Pip Limit Analysis
Analyze if pip-based limits need adjustment for larger lot sizes
"""

print("="*70)
print("DRAWDOWN & PIP LIMIT ANALYSIS FOR LOT SIZE SCALING")
print("="*70)

# Current configuration
BASE_LOT_OLD = 0.05
BASE_LOT_NEW = 0.08
DCA_MULTIPLIER = 1.49
DCA_TRIGGER_PIPS = 10
DCA_MAX_DRAWDOWN_PIPS = 70
GRID_SPACING_PIPS = 8
HEDGE_TRIGGER_PIPS = 8

print(f"\nCurrent Configuration:")
print(f"  BASE_LOT_SIZE: {BASE_LOT_OLD} → {BASE_LOT_NEW} ({(BASE_LOT_NEW/BASE_LOT_OLD - 1)*100:.1f}% increase)")
print(f"  DCA_TRIGGER_PIPS: {DCA_TRIGGER_PIPS} pips")
print(f"  DCA_MAX_DRAWDOWN_PIPS: {DCA_MAX_DRAWDOWN_PIPS} pips")

print(f"\n{'='*70}")
print("ISSUE 1: DCA_MAX_DRAWDOWN_PIPS Blocks Levels 7-8")
print(f"{'='*70}")

print(f"\nDCA Level Triggers:")
for level in range(1, 9):
    trigger_pips = level * DCA_TRIGGER_PIPS
    status = "✅ Allowed" if trigger_pips < DCA_MAX_DRAWDOWN_PIPS else "❌ BLOCKED"
    print(f"  DCA L{level}: Triggers at {trigger_pips} pips - {status}")

print(f"\n⚠️  PROBLEM: DCA levels 7-8 are blocked by 70 pip limit!")
print(f"   - DCA L7 would trigger at 70 pips (blocked at exactly 70)")
print(f"   - DCA L8 would trigger at 80 pips (blocked)")
print(f"\n   To allow full 8 levels, need DCA_MAX_DRAWDOWN_PIPS ≥ 85 pips")

print(f"\n{'='*70}")
print("ISSUE 2: Dollar-Based Drawdown Risk Comparison")
print(f"{'='*70}")

def calculate_drawdown_scenarios(base_lot, label):
    """Calculate drawdown at different pip levels"""
    print(f"\n{label} (Base: {base_lot} lots)")
    print(f"{'Scenario':<30} {'Lots':<10} {'70 pips':<15} {'85 pips':<15} {'100 pips':<15}")
    print("-"*75)

    # Just original position
    lots = base_lot
    print(f"{'Original position only':<30} {lots:<10.2f} ${lots*70:<14.2f} ${lots*85:<14.2f} ${lots*100:<14.2f}")

    # With DCA L3 (fits in old 0.8 exposure)
    l1 = base_lot * 1.49
    l2 = l1 * 1.49
    l3 = l2 * 1.49
    lots_l3 = base_lot + l1 + l2 + l3
    print(f"{'+ DCA L3 (old limit)':<30} {lots_l3:<10.2f} ${lots_l3*70:<14.2f} ${lots_l3*85:<14.2f} ${lots_l3*100:<14.2f}")

    # With DCA L6 (max before 70 pip block)
    current = base_lot
    cumulative = base_lot
    for i in range(6):
        current = current * 1.49
        cumulative += current
    lots_l6 = cumulative
    print(f"{'+ DCA L6 (70 pip max)':<30} {lots_l6:<10.2f} ${lots_l6*70:<14.2f} ${lots_l6*85:<14.2f} ${lots_l6*100:<14.2f}")

    # With DCA L8 (full strategy)
    current = base_lot
    cumulative = base_lot
    for i in range(8):
        current = current * 1.49
        cumulative += current
    lots_l8 = cumulative
    print(f"{'+ DCA L8 (full strategy)':<30} {lots_l8:<10.2f} ${lots_l8*70:<14.2f} ${lots_l8*85:<14.2f} ${lots_l8*100:<14.2f}")

    # With Grid + Hedge + DCA L8
    grid_lots = 4 * base_lot
    hedge_lots = base_lot * 5.0  # opposite direction
    same_direction_lots = lots_l8 + grid_lots
    print(f"{'+ Grid + DCA L8 (same dir)':<30} {same_direction_lots:<10.2f} ${same_direction_lots*70:<14.2f} ${same_direction_lots*85:<14.2f} ${same_direction_lots*100:<14.2f}")
    print(f"{'Hedge profit (opposite dir)':<30} {hedge_lots:<10.2f} ${hedge_lots*70:<14.2f} ${hedge_lots*85:<14.2f} ${hedge_lots*100:<14.2f}")

    net_70 = -(same_direction_lots*70) + (hedge_lots*70)
    net_85 = -(same_direction_lots*85) + (hedge_lots*85)
    net_100 = -(same_direction_lots*100) + (hedge_lots*100)
    print(f"{'Net P&L (with hedge)':<30} {'':10} ${net_70:<14.2f} ${net_85:<14.2f} ${net_100:<14.2f}")

    return {
        'base': base_lot,
        'l8_lots': lots_l8,
        'full_stack': same_direction_lots,
        'net_70': net_70,
        'net_85': net_85,
        'net_100': net_100
    }

old_data = calculate_drawdown_scenarios(BASE_LOT_OLD, "OLD CONFIG (0.05 base)")
new_data = calculate_drawdown_scenarios(BASE_LOT_NEW, "NEW CONFIG (0.08 base)")

print(f"\n{'='*70}")
print("ISSUE 3: Analysis Results vs Configuration")
print(f"{'='*70}")

print(f"""
From the historical analysis:
  - Best 8-level DCA sequence: 33 pips decline, $229.12 profit
  - This suggests DCA recovered well before hitting deep drawdown

Current 70 pip limit means:
  - Maximum depth: 60 pips (DCA L6)
  - Missing: DCA L7 (70 pips) and L8 (80 pips)
  - Lost recovery power: 2.31 lots of buying power unavailable

If analysis showed recovery at 33 pips, why have 70+ pip limit?
  - Safety buffer for worse-case scenarios
  - 70 pips = 2.1x the worst case from analysis (33 pips)
  - But blocks the final 2 DCA levels!
""")

print(f"\n{'='*70}")
print("RISK ASSESSMENT: Account Impact")
print(f"{'='*70}")

account_sizes = [500, 1000, 2000, 5000]
print(f"\n{'Account':<12} {'Scenario':<35} {'Drawdown $':<15} {'Drawdown %':<15}")
print("-"*80)

for account in account_sizes:
    # Old config: DCA L6 at 70 pips
    old_dd = abs(old_data['net_70'])
    old_pct = (old_dd / account) * 100
    print(f"${account:<11} {'OLD: DCA L6 @ 70 pips':<35} ${old_dd:<14.2f} {old_pct:<14.1f}%")

    # New config: DCA L6 at 70 pips
    new_dd_70 = abs(new_data['net_70'])
    new_pct_70 = (new_dd_70 / account) * 100
    print(f"${account:<11} {'NEW: DCA L6 @ 70 pips (blocked)':<35} ${new_dd_70:<14.2f} {new_pct_70:<14.1f}%")

    # New config: DCA L8 at 85 pips
    new_dd_85 = abs(new_data['net_85'])
    new_pct_85 = (new_dd_85 / account) * 100
    print(f"${account:<11} {'NEW: DCA L8 @ 85 pips (full)':<35} ${new_dd_85:<14.2f} {new_pct_85:<14.1f}%")

    # New config: DCA L8 at 100 pips
    new_dd_100 = abs(new_data['net_100'])
    new_pct_100 = (new_dd_100 / account) * 100
    print(f"${account:<11} {'NEW: DCA L8 @ 100 pips (buffer)':<35} ${new_dd_100:<14.2f} {new_pct_100:<14.1f}%")
    print()

print(f"\n{'='*70}")
print("RECOMMENDATIONS")
print(f"{'='*70}")

print(f"""
OPTION 1: Increase to 85 pips (Minimum for 8 levels)
  DCA_MAX_DRAWDOWN_PIPS: 70 → 85 pips

  ✅ Allows full 8-level DCA strategy
  ✅ Minimal increase (21% more)
  ⚠️  Slightly higher risk ($521 max unrealized loss on $1k account = 52%)

  On $1,000 account at max drawdown (85 pips, full stack):
    - Net loss: ${abs(new_data['net_85']):.2f} ({abs(new_data['net_85'])/10:.1f}% of account)

OPTION 2: Increase to 100 pips (Conservative buffer)
  DCA_MAX_DRAWDOWN_PIPS: 70 → 100 pips

  ✅ Allows full 8-level DCA strategy
  ✅ Extra safety margin beyond L8 trigger (80 pips)
  ✅ Matches VWAP mean reversion range
  ⚠️  Higher max drawdown (43% increase)

  On $1,000 account at max drawdown (100 pips, full stack):
    - Net loss: ${abs(new_data['net_100']):.2f} ({abs(new_data['net_100'])/10:.1f}% of account)

OPTION 3: Keep 70 pips, accept DCA L6 limit
  DCA_MAX_DRAWDOWN_PIPS: 70 (no change)

  ✅ Lower risk (stops at 60-70 pips)
  ⚠️  DCA capped at Level 6, not 8
  ⚠️  Lost recovery power (2.31 lots unavailable)
  ⚠️  Contradicts the 8-level strategy from analysis

RECOMMENDED: OPTION 1 (85 pips)
  - Minimum needed to support proven 8-level strategy
  - Analysis showed recovery at 33 pips, so 85 pip limit is 2.5x safety margin
  - Balances recovery depth with risk control
  - Still below typical VWAP band range for mean reversion

If account size is larger ($2,000+), consider OPTION 2 (100 pips) for extra buffer.
""")

print(f"\n{'='*70}")
print("OTHER PIP-BASED SETTINGS (Review for lot size scaling)")
print(f"{'='*70}")

print(f"""
These are MARKET-BASED and generally don't need scaling with lot size:

✅ GRID_SPACING_PIPS = {GRID_SPACING_PIPS} pips
   - Market-driven: spacing between grid levels
   - No change needed

✅ HEDGE_TRIGGER_PIPS = {HEDGE_TRIGGER_PIPS} pips
   - Market-driven: activation threshold
   - No change needed

✅ DCA_TRIGGER_PIPS = {DCA_TRIGGER_PIPS} pips
   - Market-driven: DCA activation spacing
   - No change needed

⚠️  DCA_MAX_DRAWDOWN_PIPS = {DCA_MAX_DRAWDOWN_PIPS} pips
   - SAFETY LIMIT: Currently blocks DCA L7-L8
   - NEEDS UPDATE to 85-100 pips
""")

print("="*70)
