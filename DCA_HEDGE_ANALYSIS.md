# DCA/Hedge/Grid System - Deep Dive Analysis

## System Overview

The bot uses THREE recovery mechanisms simultaneously:
1. **Grid**: Add positions at fixed pip intervals (8 pips)
2. **Hedge**: Open opposite direction at 8 pips loss (5x overhedge)
3. **DCA**: Add to losing position at 10 pip intervals (1.49x multiplier)

## Configuration

```python
# Grid System
GRID_ENABLED = True
GRID_SPACING_PIPS = 8
MAX_GRID_LEVELS = 4
GRID_LOT_SIZE = 0.03

# Hedge System
HEDGE_ENABLED = True
HEDGE_TRIGGER_PIPS = 8
HEDGE_RATIO = 5.0  # 5x overhedge
MAX_HEDGES_PER_POSITION = 1  # Only ONE hedge allowed

# DCA System
DCA_ENABLED = True
DCA_TRIGGER_PIPS = 10
DCA_MAX_LEVELS = 8
DCA_MULTIPLIER = 1.49
```

## Execution Flow (Every 60 Seconds)

### Step 1: Get All MT5 Positions
```python
positions = mt5.get_positions()  # Gets ALL open positions
```

### Step 2: For Each Position
```python
for position in positions:
    ticket = position['ticket']
    comment = position.get('comment', '')

    # Check if this is a recovery order
    is_recovery = 'Grid' in comment or 'Hedge' in comment or 'DCA' in comment

    if not is_recovery and ticket not in tracked_positions:
        # Track new original position
        recovery_manager.track_position(...)
    elif is_recovery:
        # Skip - recovery orders don't spawn more recovery
        continue

    # Check recovery triggers for ORIGINAL positions only
    if ticket in tracked_positions:
        actions = recovery_manager.check_all_recovery_triggers(...)

        for action in actions:
            execute_recovery_action(action)  # Places MT5 order immediately
```

### Step 3: Recovery Trigger Checks

#### Grid Trigger Logic
```python
def check_grid_trigger(ticket, current_price):
    position = tracked_positions[ticket]

    # Already at max?
    if len(position['grid_levels']) >= MAX_GRID_LEVELS:  # 4
        return None

    # Calculate pips moved
    pips_moved = (current_price - entry_price) / 0.0001

    # Expected number of grid levels based on distance
    expected_levels = int(pips_moved / GRID_SPACING_PIPS) + 1
    #                  = int(8 / 8) + 1 = 2
    #                  = int(16 / 8) + 1 = 3

    # Need more levels?
    if expected_levels > len(position['grid_levels']) + 1:
        # Add to tracking BEFORE order is placed
        position['grid_levels'].append({...})

        return {
            'action': 'grid',
            'comment': f'Grid L{len(grid_levels)} - {ticket}'
        }

    return None
```

#### Hedge Trigger Logic
```python
def check_hedge_trigger(ticket, current_price):
    position = tracked_positions[ticket]

    # Already hedged?
    if len(position['hedge_tickets']) >= MAX_HEDGES_PER_POSITION:  # 1
        return None

    # Calculate underwater pips
    pips_underwater = (current_price - entry_price) / 0.0001

    # Trigger reached?
    if pips_underwater >= HEDGE_TRIGGER_PIPS:  # 8
        # Add to tracking BEFORE order is placed
        position['hedge_tickets'].append({...})

        return {
            'action': 'hedge',
            'comment': f'Hedge - {ticket}'
        }

    return None
```

## User's Actual Trade Sequence

Initial position opened at **1.17313**:

| Time | Price | Pips | What Should Trigger | What Actually Happened |
|------|-------|------|---------------------|------------------------|
| 12:01:32 | 1.17313 | 0 | Initial SELL 0.03 | ✅ Opened |
| 12:02:32 | ~1.17321 | +8 | Grid L1 + Hedge | ✅ Both opened |
| ? | 1.17319 | +6 | Nothing | ❌ Grid L1 AGAIN (duplicate!) |
| ? | 1.17322 | +9 | Nothing | ❌ Hedge AGAIN (duplicate!) |
| 12:18:38 | 1.17330 | +17 | Grid L2 + DCA L1 | ✅ Both opened |

## The Bug - Root Cause Analysis

### Issue #1: Grid L1 Duplicate

**First Grid L1 at 1.17314** (1 pip from entry):
- pips_moved = 1
- expected_levels = int(1/8) + 1 = 0 + 1 = 1
- len(grid_levels) = 0
- Check: 1 > 0 + 1? → 1 > 1? → **FALSE** ❌
- **SHOULD NOT TRIGGER!**

🚨 **BUG #1: Grid triggering at 1 pip when it should wait for 8 pips!**

**Second Grid L1 at 1.17319** (6 pips from entry):
- pips_moved = 6
- expected_levels = int(6/8) + 1 = 0 + 1 = 1
- len(grid_levels) = 1 (if first was counted)
- Check: 1 > 1 + 1? → 1 > 2? → **FALSE** ❌
- Should NOT trigger again

But if first Grid L1 wasn't properly tracked:
- len(grid_levels) = 0
- Check: 1 > 0 + 1? → 1 > 1? → **FALSE**
- Still shouldn't trigger!

🚨 **BUG #2: Grid logic has off-by-one error or pips calculation wrong!**

### Issue #2: Hedge Duplicate

**First Hedge at 1.17318** (5 pips):
- pips_underwater = 5
- Trigger at 8 pips? → **FALSE** ❌
- **SHOULD NOT TRIGGER YET!**

🚨 **BUG #3: Hedge triggering before reaching 8 pips!**

**Second Hedge at 1.17322** (9 pips):
- pips_underwater = 9
- Trigger at 8 pips? → **TRUE** ✅
- len(hedge_tickets) = 1 (if first was counted)
- Check: 1 >= 1? → **TRUE** - should BLOCK! ❌
- **SHOULD NOT OPEN SECOND HEDGE!**

🚨 **BUG #4: Hedge tickets not preventing duplicates!**

## Critical Findings

### Finding 1: Premature Triggering
Grid and Hedge are triggering BEFORE reaching their pip thresholds:
- Grid L1 at 1 pip (should be 8)
- Hedge at 5 pips (should be 8)

### Finding 2: Duplicate Prevention Failing
Even when triggered correctly, duplicates aren't being prevented:
- Grid L1 appears twice
- Hedge appears twice despite MAX_HEDGES_PER_POSITION = 1

### Finding 3: Tracking State Issues
Possibilities:
1. **Race condition**: Multiple scans processing same position simultaneously
2. **List not persisting**: grid_levels/hedge_tickets cleared between scans
3. **Ticket mismatch**: Wrong original_ticket being tracked
4. **Order placement failure**: Action added to list but order fails, list not rolled back

## Hypothesis: The Most Likely Cause

**THEORY: The condition logic has an off-by-one error**

Looking at Grid trigger line 163:
```python
if expected_levels > len(position['grid_levels']) + 1:
```

This says: "If expected levels is GREATER than current levels + 1"

With the "+1" for the original position, this creates confusion:
- Original position counts as "level 0"
- First grid should be "level 1"
- But the check adds +1 to current length

**Example with 8 pips moved:**
- expected_levels = int(8/8) + 1 = 2
- len(grid_levels) = 0
- Check: 2 > 0 + 1? → 2 > 1? → TRUE ✅ (Correct)

**But with 1 pip moved:**
- expected_levels = int(1/8) + 1 = 1
- len(grid_levels) = 0
- Check: 1 > 0 + 1? → 1 > 1? → FALSE ❌ (Correct - shouldn't trigger)

**So the logic LOOKS correct...**

## Next Steps for Diagnosis

1. **Add detailed logging** to see actual values during trigger checks
2. **Check pip calculation** - is pip_value correct? (should be 0.0001)
3. **Verify position tracking** - print tracked_positions state before/after
4. **Check for concurrent execution** - are multiple threads accessing recovery?
5. **Audit order placement** - is action being executed multiple times?

## Recommended Immediate Actions

1. **Add logging to recovery_manager.py** at critical points:
   ```python
   print(f"[GRID CHECK] Ticket: {ticket}, Pips: {pips_moved:.1f}, Expected: {expected_levels}, Current: {len(grid_levels)}")
   ```

2. **Add unique action IDs** to prevent duplicate execution:
   ```python
   action_id = f"{action_type}_{ticket}_{datetime.now().timestamp()}"
   if action_id in executed_actions:
       return  # Already executed
   ```

3. **Verify pip calculation** - check symbol point value:
   ```python
   symbol_info = mt5.symbol_info(symbol)
   pip_value = symbol_info.point  # Should be 0.0001 for EURUSD
   ```

## Questions to Answer

1. ❓ What is the actual pip value being used in calculations?
2. ❓ What are the exact pips_moved values when Grid L1 triggers?
3. ❓ Is tracked_positions persisting between scans or getting reset?
4. ❓ Are recovery actions being executed multiple times per scan?
5. ❓ Is there a timing issue between adding to list and placing order?
