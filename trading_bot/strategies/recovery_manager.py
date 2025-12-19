"""
Recovery Strategy Manager
Implements Grid Trading, Hedging, and DCA/Martingale
All discovered from EA analysis of 428 trades
"""

from typing import Dict, List, Optional
from datetime import datetime

from config.strategy_config import (
    GRID_ENABLED,
    GRID_SPACING_PIPS,
    MAX_GRID_LEVELS,
    GRID_LOT_SIZE,
    HEDGE_ENABLED,
    HEDGE_TRIGGER_PIPS,
    HEDGE_RATIO,
    MAX_HEDGES_PER_POSITION,
    DCA_ENABLED,
    DCA_TRIGGER_PIPS,
    DCA_MAX_LEVELS,
    DCA_MULTIPLIER,
    DCA_MAX_TOTAL_EXPOSURE,
    DCA_MAX_DRAWDOWN_PIPS,
    MAX_TOTAL_LOTS,
    MAX_STACK_EXPOSURE,
)


def round_volume_to_step(volume: float, step: float = 0.01, min_lot: float = 0.01, max_lot: float = 100.0) -> float:
    """
    Round volume to broker's step size and clamp to min/max limits

    Args:
        volume: Raw volume to round
        step: Broker's volume step (default 0.01)
        min_lot: Minimum allowed lot size (default 0.01)
        max_lot: Maximum allowed lot size (default 100.0)

    Returns:
        float: Rounded and clamped volume
    """
    # Round to nearest step
    rounded = round(volume / step) * step

    # Clamp to broker limits
    rounded = max(min_lot, min(rounded, max_lot))

    # Round to 2 decimals for display
    return round(rounded, 2)


def normalize_position_type(pos_type) -> str:
    """
    Normalize position type to string ('buy' or 'sell')

    Handles both MT5 integer types (0=buy, 1=sell) and string types.

    Args:
        pos_type: Position type (int or str)

    Returns:
        str: 'buy' or 'sell'
    """
    if isinstance(pos_type, str):
        return pos_type.lower()
    elif isinstance(pos_type, int):
        return 'buy' if pos_type == 0 else 'sell'
    else:
        raise ValueError(f"Invalid position type: {pos_type} (type: {type(pos_type)})")


class RecoveryManager:
    """Manage recovery strategies: Grid, Hedge, DCA/Martingale"""

    def __init__(self):
        """Initialize recovery manager"""
        self.tracked_positions = {}  # Track positions and their recovery state

    def track_position(
        self,
        ticket: int,
        symbol: str,
        entry_price: float,
        position_type: str,
        volume: float,
        metadata: dict = None  # Added for strategy_mode tracking
    ):
        """
        Start tracking a position for recovery

        Args:
            ticket: Position ticket
            symbol: Trading symbol
            entry_price: Entry price
            position_type: 'buy' or 'sell'
            volume: Initial lot size
            metadata: Optional metadata dict (e.g., strategy_mode)
        """
        self.tracked_positions[ticket] = {
            'ticket': ticket,
            'symbol': symbol,
            'entry_price': entry_price,
            'type': position_type,
            'initial_volume': volume,
            'grid_levels': [],
            'hedge_tickets': [],
            'dca_levels': [],
            'total_volume': volume,
            'max_underwater_pips': 0,
            'recovery_active': False,
            'open_time': datetime.now(),  # Track when position opened
            'last_recovery_check': {  # Prevent duplicate recovery orders
                'grid': None,  # Last time grid was checked/added
                'hedge': None,  # Last time hedge was checked/added
                'dca': None,  # Last time DCA was checked/added
            },
            'partial_close_state': {  # Track partial closures
                'levels_closed': [],  # Which profit levels have been closed
                'tickets_closed': [],  # Which tickets have been closed
                'total_closed_volume': 0.0,  # Total volume closed via partial
            },
            'metadata': metadata or {},  # Store strategy mode and other metadata
        }

    def adopt_existing_positions(self, mt5_positions: List[Dict], magic_number: int = None) -> int:
        """
        Adopt existing MT5 positions into tracking system (for crash recovery)

        This method reconstructs recovery state from existing positions,
        allowing the bot to resume management after restarts.

        Args:
            mt5_positions: List of all current MT5 positions
            magic_number: Bot's magic number to filter trades (None = adopt all)

        Returns:
            int: Number of positions adopted
        """
        adopted_count = 0

        for pos in mt5_positions:
            ticket = pos['ticket']

            # Skip if already tracked
            if ticket in self.tracked_positions:
                continue

            # Filter by magic number if specified
            if magic_number is not None and pos.get('magic', 0) != magic_number:
                continue

            # Extract position details
            symbol = pos['symbol']
            entry_price = pos['price_open']
            position_type = normalize_position_type(pos['type'])  # Safe type conversion
            volume = pos['volume']

            # Check if this looks like a recovery position (from comment)
            comment = pos.get('comment', '')

            # Use the is_recovery_position helper to check
            is_recovery, parent_ticket = self.is_recovery_position(comment)

            # If this is a recovery position, try to link to parent
            if is_recovery and parent_ticket and parent_ticket in self.tracked_positions:
                # This is a recovery order for an already-tracked parent
                position = self.tracked_positions[parent_ticket]

                # Detect recovery type from comment (old or new format)
                is_grid = 'Grid' in comment or comment.startswith('G')
                is_dca = 'DCA' in comment or comment.startswith('D')
                is_hedge = 'Hedge' in comment or comment.startswith('H')

                if is_grid:
                    # Add to grid levels
                    level_num = len(position['grid_levels']) + 1
                    position['grid_levels'].append({
                        'ticket': ticket,
                        'price': entry_price,
                        'volume': volume,
                        'time': datetime.now()
                    })
                    position['total_volume'] += volume
                    print(f"   🔗 Linked Grid L{level_num} (#{ticket}) to parent #{parent_ticket}")

                elif is_dca:
                    # Add to DCA levels
                    level_num = len(position['dca_levels']) + 1
                    position['dca_levels'].append({
                        'ticket': ticket,
                        'price': entry_price,
                        'volume': volume,
                        'level': level_num,
                        'time': datetime.now()
                    })
                    position['total_volume'] += volume
                    print(f"   🔗 Linked DCA L{level_num} (#{ticket}) to parent #{parent_ticket}")

                elif is_hedge:
                    # Add to hedges
                    hedge_type = 'sell' if position_type == 'buy' else 'buy'
                    position['hedge_tickets'].append({
                        'ticket': ticket,
                        'type': hedge_type,
                        'volume': volume,
                        'trigger_pips': 0,  # Unknown, will recalculate
                        'time': datetime.now()
                    })
                    print(f"   🔗 Linked Hedge (#{ticket}) to parent #{parent_ticket}")

            elif is_recovery and parent_ticket:
                # ORPHAN PREVENTION: This is a recovery trade but parent not found
                # DO NOT adopt as parent - this prevents recovery trades from spawning their own recovery!
                print(f"   ⚠️  ORPHAN DETECTED: Recovery trade #{ticket} has no parent #{parent_ticket} - skipping adoption")

            else:
                # This looks like an original/parent position (no recovery markers) - track it
                self.track_position(
                    ticket=ticket,
                    symbol=symbol,
                    entry_price=entry_price,
                    position_type=position_type,
                    volume=volume
                )
                adopted_count += 1
                print(f"   ✅ Adopted position #{ticket} ({symbol} {position_type.upper()} {volume:.2f} @ {entry_price})")

        return adopted_count

    def untrack_position(self, ticket: int):
        """Remove position from tracking"""
        if ticket in self.tracked_positions:
            del self.tracked_positions[ticket]

    def get_total_exposure(self, all_positions: List[Dict]) -> float:
        """
        Calculate total exposure across all open positions

        Args:
            all_positions: List of all MT5 positions

        Returns:
            float: Total exposure in lots
        """
        total = 0.0
        for pos in all_positions:
            total += pos.get('volume', 0.0)
        return total

    def check_exposure_limits(
        self,
        ticket: int,
        proposed_volume: float,
        all_positions: List[Dict]
    ) -> tuple[bool, str]:
        """
        Check if adding proposed volume would exceed exposure limits

        Args:
            ticket: Parent position ticket
            proposed_volume: Volume of proposed recovery trade
            all_positions: List of all MT5 positions

        Returns:
            Tuple of (can_add, reason)
        """
        # Check stack exposure limit
        if ticket in self.tracked_positions:
            position = self.tracked_positions[ticket]
            current_stack_volume = position['total_volume']
            new_stack_volume = current_stack_volume + proposed_volume

            if new_stack_volume > MAX_STACK_EXPOSURE:
                return False, f"Stack exposure limit: {new_stack_volume:.2f} > {MAX_STACK_EXPOSURE:.2f} lots"

        # Check total exposure limit
        current_total = self.get_total_exposure(all_positions)
        new_total = current_total + proposed_volume

        if new_total > MAX_TOTAL_LOTS:
            return False, f"Total exposure limit: {new_total:.2f} > {MAX_TOTAL_LOTS:.2f} lots"

        return True, "OK"

    def is_recovery_position(self, comment: str) -> tuple[bool, Optional[int]]:
        """
        Check if a position is a recovery trade (Grid/Hedge/DCA)

        Args:
            comment: Position comment field

        Returns:
            Tuple of (is_recovery, parent_ticket)
            Note: parent_ticket may be shortened (last 5 digits only)
        """
        if not comment:
            return False, None

        # Try new format first (G1-91276, D2-91276, H-91276) - shortened ticket
        if '-' in comment and any(comment.startswith(prefix) for prefix in ['G', 'D', 'H']):
            try:
                ticket_suffix = int(comment.split('-')[-1])

                # If suffix is 5 digits or less, try to match against tracked positions
                if ticket_suffix < 100000:  # Shortened format (last 5 digits)
                    # Try to find matching parent in tracked positions
                    for tracked_ticket in self.tracked_positions:
                        if tracked_ticket % 100000 == ticket_suffix:
                            return True, tracked_ticket
                    # If no match found, return the suffix (orphan detection will handle it)
                    return True, ticket_suffix
                else:
                    # Full ticket number (legacy format)
                    return True, ticket_suffix

            except (ValueError, IndexError):
                pass

        # Fall back to old format (Grid L1 - 12345, DCA L2 - 12345, Hedge - 12345)
        if ' - ' in comment and any(keyword in comment for keyword in ['Grid', 'DCA', 'Hedge']):
            try:
                parent_ticket = int(comment.split(' - ')[-1])
                return True, parent_ticket
            except (ValueError, IndexError):
                pass

        return False, None

    def get_all_recovery_tickets(self, parent_ticket: int) -> List[int]:
        """
        Get all recovery trade tickets for a parent position

        Args:
            parent_ticket: Parent position ticket

        Returns:
            List of all recovery trade tickets
        """
        if parent_ticket not in self.tracked_positions:
            return []

        position = self.tracked_positions[parent_ticket]
        tickets = []

        # Collect grid tickets
        for grid in position['grid_levels']:
            if 'ticket' in grid:
                tickets.append(grid['ticket'])

        # Collect hedge tickets
        for hedge in position['hedge_tickets']:
            if 'ticket' in hedge:
                tickets.append(hedge['ticket'])

        # Collect DCA tickets
        for dca in position['dca_levels']:
            if 'ticket' in dca:
                tickets.append(dca['ticket'])

        return tickets

    def detect_orphaned_positions(self, mt5_positions: List[Dict]) -> List[Dict]:
        """
        Detect orphaned recovery trades (parent no longer exists)

        Args:
            mt5_positions: List of all current MT5 positions

        Returns:
            List of orphaned position dicts with ticket and reason
        """
        orphans = []

        for pos in mt5_positions:
            ticket = pos['ticket']
            comment = pos.get('comment', '')

            # Check if this is a recovery position
            is_recovery, parent_ticket = self.is_recovery_position(comment)

            if is_recovery and parent_ticket:
                # Check if parent exists in tracked positions
                if parent_ticket not in self.tracked_positions:
                    orphans.append({
                        'ticket': ticket,
                        'parent_ticket': parent_ticket,
                        'reason': f'Parent #{parent_ticket} not tracked',
                        'comment': comment,
                        'symbol': pos['symbol'],
                        'type': pos['type'],
                        'volume': pos['volume'],
                        'profit': pos.get('profit', 0.0)
                    })
                    continue

                # Check if parent position still exists in MT5
                parent_exists = any(p['ticket'] == parent_ticket for p in mt5_positions)
                if not parent_exists:
                    orphans.append({
                        'ticket': ticket,
                        'parent_ticket': parent_ticket,
                        'reason': f'Parent #{parent_ticket} closed',
                        'comment': comment,
                        'symbol': pos['symbol'],
                        'type': pos['type'],
                        'volume': pos['volume'],
                        'profit': pos.get('profit', 0.0)
                    })

        return orphans

    def close_orphaned_positions(self, mt5_manager, mt5_positions: List[Dict]) -> int:
        """
        Detect and close all orphaned recovery trades

        Args:
            mt5_manager: MT5Manager instance for closing positions
            mt5_positions: List of all current MT5 positions

        Returns:
            int: Number of orphans closed
        """
        orphans = self.detect_orphaned_positions(mt5_positions)

        if not orphans:
            return 0

        print(f"\n{'='*80}")
        print(f"🧹 ORPHAN CLEANUP: Found {len(orphans)} orphaned recovery trade(s)")
        print(f"{'='*80}")

        closed_count = 0
        failed_count = 0

        for orphan in orphans:
            ticket = orphan['ticket']
            parent_ticket = orphan['parent_ticket']
            reason = orphan['reason']
            profit = orphan['profit']

            print(f"   Orphan #{ticket}: {reason} (P&L: ${profit:.2f})")

            # Close the orphan
            if mt5_manager.close_position(ticket):
                closed_count += 1
                print(f"   ✅ Closed orphan #{ticket}")
            else:
                failed_count += 1
                print(f"   ❌ Failed to close orphan #{ticket}")

        print(f"\n📊 Orphan Cleanup Results:")
        print(f"   Closed: {closed_count} orphan(s)")
        print(f"   Failed: {failed_count} orphan(s)")
        print(f"{'='*80}\n")

        return closed_count

    def validate_recovery_direction(self, action: Dict) -> tuple[bool, str]:
        """
        Validate that recovery trade direction matches parent position

        Args:
            action: Recovery action dict with 'action', 'original_ticket', and 'type'

        Returns:
            Tuple of (is_valid, error_message)
        """
        action_type = action.get('action')
        original_ticket = action.get('original_ticket')
        recovery_type = action.get('type')

        if original_ticket not in self.tracked_positions:
            return False, f"Parent position #{original_ticket} not tracked"

        parent_position = self.tracked_positions[original_ticket]
        parent_type = parent_position['type']

        # Validate direction rules
        if action_type == 'grid':
            # Grid must match parent direction
            if recovery_type != parent_type:
                return False, f"Grid direction mismatch: parent={parent_type}, grid={recovery_type}"

        elif action_type == 'dca':
            # DCA must match parent direction
            if recovery_type != parent_type:
                return False, f"DCA direction mismatch: parent={parent_type}, dca={recovery_type}"

        elif action_type == 'hedge':
            # Hedge must be opposite to parent
            expected_hedge = 'sell' if parent_type == 'buy' else 'buy'
            if recovery_type != expected_hedge:
                return False, f"Hedge direction mismatch: parent={parent_type}, hedge={recovery_type} (expected {expected_hedge})"

        return True, "OK"

    def store_recovery_ticket(self, original_ticket: int, recovery_ticket: int, action_type: str):
        """
        Store ticket number for a recovery order after it's been placed

        Args:
            original_ticket: Original position ticket
            recovery_ticket: New recovery order ticket
            action_type: 'grid', 'hedge', or 'dca'
        """
        if original_ticket not in self.tracked_positions:
            return

        position = self.tracked_positions[original_ticket]

        if action_type == 'grid' and position['grid_levels']:
            # Store ticket in the most recent grid level
            position['grid_levels'][-1]['ticket'] = recovery_ticket

        elif action_type == 'hedge' and position['hedge_tickets']:
            # Store ticket in the most recent hedge
            position['hedge_tickets'][-1]['ticket'] = recovery_ticket

        elif action_type == 'dca' and position['dca_levels']:
            # Store ticket in the most recent DCA level
            position['dca_levels'][-1]['ticket'] = recovery_ticket

    def check_grid_trigger(
        self,
        ticket: int,
        current_price: float,
        pip_value: float = 0.0001
    ) -> Optional[Dict]:
        """
        Check if we should add a grid level

        Args:
            ticket: Position ticket
            current_price: Current market price
            pip_value: Pip value for symbol (0.0001 for most pairs)

        Returns:
            Dict with grid order details or None
        """
        if not GRID_ENABLED or ticket not in self.tracked_positions:
            return None

        position = self.tracked_positions[ticket]

        # DUPLICATE PREVENTION: Check cooldown (30 seconds between grid adds)
        last_check = position.get('last_recovery_check', {}).get('grid')
        if last_check:
            time_since_last = (datetime.now() - last_check).total_seconds()
            if time_since_last < 30:
                return None  # Too soon, skip

        # Check if maxed out grid levels
        if len(position['grid_levels']) >= MAX_GRID_LEVELS:
            return None

        entry_price = position['entry_price']
        position_type = position['type']

        # Calculate pips moved
        if position_type == 'buy':
            pips_moved = (entry_price - current_price) / pip_value
        else:
            pips_moved = (current_price - entry_price) / pip_value

        # Check if underwater
        if pips_moved <= 0:
            return None

        # Calculate expected grid levels
        expected_levels = int(pips_moved / GRID_SPACING_PIPS) + 1

        # Need to add grid level?
        if expected_levels > len(position['grid_levels']) + 1:  # +1 for original position
            # Calculate grid price
            levels_added = len(position['grid_levels']) + 1
            grid_distance = GRID_SPACING_PIPS * levels_added * pip_value

            if position_type == 'buy':
                grid_price = entry_price - grid_distance
            else:
                grid_price = entry_price + grid_distance

            # Round grid volume to broker step size
            grid_volume = round_volume_to_step(GRID_LOT_SIZE)

            # Add to tracked levels
            position['grid_levels'].append({
                'price': grid_price,
                'volume': grid_volume,
                'time': datetime.now()
            })

            position['total_volume'] += grid_volume
            position['recovery_active'] = True

            # Update cooldown timestamp to prevent duplicates
            position['last_recovery_check']['grid'] = datetime.now()

            print(f"\n  ✅ GRID TRIGGERED!")
            print(f"  🔹 Grid Level {len(position['grid_levels'])} triggered for {ticket}")
            print(f"     Entry: {entry_price:.5f} → Grid: {grid_price:.5f}")
            print(f"     Distance: {GRID_SPACING_PIPS * levels_added:.1f} pips")
            print(f"     Volume: {grid_volume}")
            print(f"     Total grid levels now: {len(position['grid_levels'])}")

            return {
                'action': 'grid',
                'original_ticket': ticket,  # Track which position this belongs to
                'symbol': position['symbol'],
                'type': position_type,
                'price': grid_price,
                'volume': grid_volume,
                'level': len(position['grid_levels']),  # Current level number
                'pips': pips_moved,  # Pips moved against position
                'comment': f'G{len(position["grid_levels"])}-{ticket % 100000}'  # Last 5 digits only
            }

        return None

    def check_hedge_trigger(
        self,
        ticket: int,
        current_price: float,
        pip_value: float = 0.0001
    ) -> Optional[Dict]:
        """
        Check if we should activate a hedge

        Args:
            ticket: Position ticket
            current_price: Current market price
            pip_value: Pip value for symbol

        Returns:
            Dict with hedge order details or None
        """
        if not HEDGE_ENABLED or ticket not in self.tracked_positions:
            return None

        position = self.tracked_positions[ticket]

        # DUPLICATE PREVENTION: Check cooldown (60 seconds between hedges - they're expensive)
        last_check = position.get('last_recovery_check', {}).get('hedge')
        if last_check:
            time_since_last = (datetime.now() - last_check).total_seconds()
            if time_since_last < 60:
                return None  # Too soon, skip

        # Check if already hedged
        if len(position['hedge_tickets']) >= MAX_HEDGES_PER_POSITION:
            return None

        entry_price = position['entry_price']
        position_type = position['type']

        # Calculate pips underwater
        if position_type == 'buy':
            pips_underwater = (entry_price - current_price) / pip_value
        else:
            pips_underwater = (current_price - entry_price) / pip_value

        # Update max underwater
        if pips_underwater > position['max_underwater_pips']:
            position['max_underwater_pips'] = pips_underwater

        # Check if trigger reached
        if pips_underwater >= HEDGE_TRIGGER_PIPS:
            # Calculate hedge volume (overhedge) - based on INITIAL volume, not total
            # Original EA hedges the initial position size, not accumulated grid/DCA
            hedge_volume = position['initial_volume'] * HEDGE_RATIO

            # Round to broker step size (0.01)
            hedge_volume = round_volume_to_step(hedge_volume)

            # SAFETY CAP: Prevent excessive hedge volumes on small accounts
            # Cap hedge volumes at 0.60 lots max to prevent margin blowout
            MAX_HEDGE_VOLUME = 0.60
            if hedge_volume > MAX_HEDGE_VOLUME:
                print(f"⚠️  Hedge volume capped: {hedge_volume:.2f} → {MAX_HEDGE_VOLUME:.2f} lots")
                hedge_volume = MAX_HEDGE_VOLUME

            # Opposite direction
            hedge_type = 'sell' if position_type == 'buy' else 'buy'

            # Mark as hedged
            position['hedge_tickets'].append({
                'type': hedge_type,
                'volume': hedge_volume,
                'trigger_pips': pips_underwater,
                'time': datetime.now()
            })

            position['recovery_active'] = True

            # Update cooldown timestamp to prevent duplicates
            position['last_recovery_check']['hedge'] = datetime.now()

            print(f"\n  ✅ HEDGE TRIGGERED!")
            print(f"  🛡️ Hedge activated for {ticket}")
            print(f"     Original: {position_type.upper()} {position['initial_volume']:.2f} (total exposure: {position['total_volume']:.2f})")
            print(f"     Hedge: {hedge_type.upper()} {hedge_volume:.2f} (ratio: {HEDGE_RATIO}x on initial)")
            print(f"     Triggered at: {pips_underwater:.1f} pips underwater")
            print(f"     Total hedges now: {len(position['hedge_tickets'])}")

            return {
                'action': 'hedge',
                'original_ticket': ticket,  # Track which position this belongs to
                'symbol': position['symbol'],
                'type': hedge_type,
                'volume': hedge_volume,
                'ratio': HEDGE_RATIO,  # Hedge ratio (e.g., 5.0x)
                'trigger_pips': pips_underwater,  # Pips underwater when triggered
                'comment': f'H-{ticket % 100000}'  # Last 5 digits only
            }

        return None

    def check_dca_trigger(
        self,
        ticket: int,
        current_price: float,
        pip_value: float = 0.0001
    ) -> Optional[Dict]:
        """
        Check if we should add DCA/Martingale level

        Args:
            ticket: Position ticket
            current_price: Current market price
            pip_value: Pip value for symbol

        Returns:
            Dict with DCA order details or None
        """
        if not DCA_ENABLED or ticket not in self.tracked_positions:
            return None

        position = self.tracked_positions[ticket]

        # DUPLICATE PREVENTION: Check cooldown (30 seconds between DCA adds)
        last_check = position.get('last_recovery_check', {}).get('dca')
        if last_check:
            time_since_last = (datetime.now() - last_check).total_seconds()
            if time_since_last < 30:
                return None  # Too soon, skip

        # Check if maxed out DCA levels
        if DCA_MAX_LEVELS and len(position['dca_levels']) >= DCA_MAX_LEVELS:
            return None

        entry_price = position['entry_price']
        position_type = position['type']

        # Calculate pips moved
        if position_type == 'buy':
            pips_moved = (entry_price - current_price) / pip_value
        else:
            pips_moved = (current_price - entry_price) / pip_value

        # Check if drawdown exceeds safety limit
        if DCA_MAX_DRAWDOWN_PIPS and pips_moved >= DCA_MAX_DRAWDOWN_PIPS:
            print(f"⚠️  DCA blocked for {ticket}: Max drawdown reached ({pips_moved:.1f} >= {DCA_MAX_DRAWDOWN_PIPS} pips)")
            return None

        # Check if underwater enough
        if pips_moved < DCA_TRIGGER_PIPS:
            return None

        # Calculate expected DCA levels
        expected_levels = int(pips_moved / DCA_TRIGGER_PIPS)

        # Need to add DCA level?
        if expected_levels > len(position['dca_levels']):
            # Calculate DCA volume (increase by multiplier)
            if len(position['dca_levels']) == 0:
                dca_volume = position['initial_volume'] * DCA_MULTIPLIER
            else:
                last_dca = position['dca_levels'][-1]
                dca_volume = last_dca['volume'] * DCA_MULTIPLIER

            # Round to broker step size (0.01)
            dca_volume = round_volume_to_step(dca_volume)

            # SAFETY CAP: Prevent excessive DCA volumes on small accounts
            # Cap DCA volumes at 0.50 lots max to prevent margin blowout
            MAX_DCA_VOLUME = 0.50
            if dca_volume > MAX_DCA_VOLUME:
                print(f"⚠️  DCA volume capped: {dca_volume:.2f} → {MAX_DCA_VOLUME:.2f} lots")
                dca_volume = MAX_DCA_VOLUME

            # Check if adding this DCA would exceed total exposure limit
            if DCA_MAX_TOTAL_EXPOSURE:
                # Calculate current DCA exposure
                current_dca_exposure = sum(level['volume'] for level in position['dca_levels'])
                new_total_dca_exposure = current_dca_exposure + dca_volume

                if new_total_dca_exposure > DCA_MAX_TOTAL_EXPOSURE:
                    print(f"⚠️  DCA blocked for {ticket}: Max total exposure reached")
                    print(f"   Current DCA exposure: {current_dca_exposure:.2f} lots")
                    print(f"   Proposed DCA volume: {dca_volume:.2f} lots")
                    print(f"   Would total: {new_total_dca_exposure:.2f} lots")
                    print(f"   Limit: {DCA_MAX_TOTAL_EXPOSURE:.2f} lots")
                    return None

            # Add to tracked levels
            position['dca_levels'].append({
                'price': current_price,
                'volume': dca_volume,
                'level': len(position['dca_levels']) + 1,
                'time': datetime.now()
            })

            position['total_volume'] += dca_volume
            position['recovery_active'] = True

            # Update cooldown timestamp to prevent duplicates
            position['last_recovery_check']['dca'] = datetime.now()

            print(f"📊 DCA Level {len(position['dca_levels'])} triggered for {ticket}")
            print(f"   Price: {current_price:.5f}")
            print(f"   Volume: {dca_volume:.2f} (multiplier: {DCA_MULTIPLIER}x)")
            print(f"   Total volume now: {position['total_volume']:.2f}")

            return {
                'action': 'dca',
                'original_ticket': ticket,  # Track which position this belongs to
                'symbol': position['symbol'],
                'type': position_type,  # Same direction
                'volume': dca_volume,
                'level': len(position['dca_levels']),  # Current DCA level
                'price': current_price,  # Entry price for this DCA level
                'total_volume': position['total_volume'],  # Total stack volume after adding DCA
                'comment': f'D{len(position["dca_levels"])}-{ticket % 100000}'  # Last 5 digits only
            }

        return None

    def is_orphaned_hedge(self, ticket: int, mt5_positions: List[Dict]) -> bool:
        """
        Check if a tracked position is an orphaned hedge

        An orphaned hedge is a hedge position whose original parent has been closed,
        leaving the hedge to fester and potentially spawn its own recovery trades.

        Args:
            ticket: Position ticket to check
            mt5_positions: List of all current MT5 positions

        Returns:
            bool: True if this is an orphaned hedge, False otherwise
        """
        if ticket not in self.tracked_positions:
            return False

        # Find this position in MT5 positions to check its comment
        position_comment = None
        for pos in mt5_positions:
            if pos['ticket'] == ticket:
                position_comment = pos.get('comment', '')
                break

        if not position_comment:
            return False

        # Check if this position has a hedge comment pattern (H-XXXXX)
        is_recovery, parent_ticket = self.is_recovery_position(position_comment)

        if is_recovery and 'H-' in position_comment and parent_ticket:
            # This is a hedge - check if parent still exists
            parent_exists = parent_ticket in self.tracked_positions
            if not parent_exists:
                # Parent closed but hedge still tracked - this is an orphaned hedge
                return True

        return False

    def check_all_recovery_triggers(
        self,
        ticket: int,
        current_price: float,
        pip_value: float = 0.0001,
        all_positions: List[Dict] = None
    ) -> List[Dict]:
        """
        Check all recovery mechanisms at once with exposure limit enforcement

        Args:
            ticket: Position ticket
            current_price: Current price
            pip_value: Pip value for symbol
            all_positions: List of all MT5 positions (for exposure checking)

        Returns:
            List of recovery actions to take
        """
        if all_positions is None:
            all_positions = []

        actions = []

        # FIX 2: Check if this is an orphaned hedge - if so, use DCA-only with strict limits
        if self.is_orphaned_hedge(ticket, all_positions):
            print(f"🛡️  Orphaned hedge detected: #{ticket}")
            print(f"   Using DCA-only recovery (no Grid, no Hedge)")
            print(f"   Limits: Max 3 levels, 1.2x multiplier, close at breakeven")

            # Only check DCA with stricter limits for orphaned hedges
            dca_action = self.check_dca_trigger(ticket, current_price, pip_value)
            if dca_action:
                position = self.tracked_positions[ticket]

                # Stricter limits for orphaned hedges
                if len(position['dca_levels']) >= 3:  # Max 3 DCA levels (not 8)
                    print(f"   ⚠️  Orphaned hedge max DCA levels reached (3/3)")
                    return actions

                # Check exposure limits
                proposed_volume = dca_action.get('volume', 0.0)
                can_add, reason = self.check_exposure_limits(ticket, proposed_volume, all_positions)
                if can_add:
                    actions.append(dca_action)
                else:
                    print(f"   ⚠️  DCA blocked for orphaned hedge {ticket}: {reason}")

            return actions  # Return early - no Grid or Hedge for orphaned hedges

        # Normal recovery for non-orphaned positions
        # Check grid
        grid_action = self.check_grid_trigger(ticket, current_price, pip_value)
        if grid_action:
            # Check exposure limits before adding
            proposed_volume = grid_action.get('volume', 0.0)
            can_add, reason = self.check_exposure_limits(ticket, proposed_volume, all_positions)
            if can_add:
                actions.append(grid_action)
            else:
                print(f"⚠️  Grid blocked for {ticket}: {reason}")

        # Check hedge
        hedge_action = self.check_hedge_trigger(ticket, current_price, pip_value)
        if hedge_action:
            proposed_volume = hedge_action.get('volume', 0.0)
            can_add, reason = self.check_exposure_limits(ticket, proposed_volume, all_positions)
            if can_add:
                actions.append(hedge_action)
            else:
                print(f"⚠️  Hedge blocked for {ticket}: {reason}")

        # Check DCA
        dca_action = self.check_dca_trigger(ticket, current_price, pip_value)
        if dca_action:
            proposed_volume = dca_action.get('volume', 0.0)
            can_add, reason = self.check_exposure_limits(ticket, proposed_volume, all_positions)
            if can_add:
                actions.append(dca_action)
            else:
                print(f"⚠️  DCA blocked for {ticket}: {reason}")

        return actions

    def get_position_status(self, ticket: int) -> Optional[Dict]:
        """
        Get recovery status for a position

        Args:
            ticket: Position ticket

        Returns:
            Dict with position recovery status
        """
        if ticket not in self.tracked_positions:
            return None

        position = self.tracked_positions[ticket]

        return {
            'ticket': ticket,
            'symbol': position['symbol'],
            'entry_price': position['entry_price'],
            'type': position['type'],
            'initial_volume': position['initial_volume'],
            'current_volume': position['total_volume'],
            'grid_levels': len(position['grid_levels']),
            'hedges_active': len(position['hedge_tickets']),
            'dca_levels': len(position['dca_levels']),
            'max_underwater_pips': position['max_underwater_pips'],
            'recovery_active': position['recovery_active'],
        }

    def get_all_positions_status(self) -> List[Dict]:
        """Get status for all tracked positions"""
        return [self.get_position_status(ticket) for ticket in self.tracked_positions.keys()]

    def calculate_breakeven_price(self, ticket: int) -> Optional[float]:
        """
        Calculate breakeven price considering all grid/DCA levels and hedges

        NOTE: This calculates the breakeven for SAME-DIRECTION positions only.
        Hedges (opposite direction) are not included in breakeven calculation
        as they need to be closed separately.

        Args:
            ticket: Position ticket

        Returns:
            float: Breakeven price or None
        """
        if ticket not in self.tracked_positions:
            return None

        position = self.tracked_positions[ticket]

        total_volume = position['initial_volume']
        weighted_price = position['entry_price'] * position['initial_volume']

        # Add grid levels (same direction as original)
        for grid_level in position['grid_levels']:
            total_volume += grid_level['volume']
            weighted_price += grid_level['price'] * grid_level['volume']

        # Add DCA levels (same direction as original)
        for dca_level in position['dca_levels']:
            total_volume += dca_level['volume']
            weighted_price += dca_level['price'] * dca_level['volume']

        # NOTE: Hedges are opposite direction and should be tracked separately
        # They don't factor into the same-direction breakeven calculation
        # The net P&L calculation in calculate_net_profit() handles the full picture

        if total_volume == 0:
            return None

        breakeven = weighted_price / total_volume
        return breakeven

    def get_all_stack_tickets(self, ticket: int) -> List[int]:
        """
        Get all ticket numbers in a recovery stack (original + grid + hedge + DCA)

        Args:
            ticket: Original position ticket

        Returns:
            List[int]: All ticket numbers in the stack
        """
        if ticket not in self.tracked_positions:
            return [ticket]  # Just the original

        position = self.tracked_positions[ticket]
        tickets = [ticket]  # Start with original

        # Add grid tickets
        for grid_level in position['grid_levels']:
            if 'ticket' in grid_level:
                tickets.append(grid_level['ticket'])

        # Add hedge tickets
        for hedge_info in position['hedge_tickets']:
            if 'ticket' in hedge_info:
                tickets.append(hedge_info['ticket'])

        # Add DCA tickets
        for dca_level in position['dca_levels']:
            if 'ticket' in dca_level:
                tickets.append(dca_level['ticket'])

        return tickets

    def calculate_net_profit(self, ticket: int, mt5_positions: List[Dict]) -> Optional[float]:
        """
        Calculate net profit/loss for entire recovery stack

        Args:
            ticket: Original position ticket
            mt5_positions: List of all current MT5 positions

        Returns:
            float: Net profit in account currency, or None if error
        """
        if ticket not in self.tracked_positions:
            return None

        # Get all tickets in this stack
        stack_tickets = self.get_all_stack_tickets(ticket)

        # Calculate total P&L across all positions in stack
        total_profit = 0.0

        for mt5_pos in mt5_positions:
            if mt5_pos['ticket'] in stack_tickets:
                total_profit += mt5_pos.get('profit', 0.0)

        return total_profit

    def check_profit_target(
        self,
        ticket: int,
        mt5_positions: List[Dict],
        account_balance: float,
        profit_percent: float = 1.0
    ) -> bool:
        """
        Check if position stack reached profit target

        Args:
            ticket: Original position ticket
            mt5_positions: List of all current MT5 positions
            account_balance: Account balance
            profit_percent: Profit target as % of balance (default 1.0%)

        Returns:
            bool: True if profit target reached
        """
        net_profit = self.calculate_net_profit(ticket, mt5_positions)

        if net_profit is None:
            return False

        # Calculate target profit in dollars
        target_profit = account_balance * (profit_percent / 100.0)

        if net_profit >= target_profit:
            print(f"✅ Profit target reached for {ticket}")
            print(f"   Net profit: ${net_profit:.2f}")
            print(f"   Target: ${target_profit:.2f} ({profit_percent}% of ${account_balance:.2f})")
            return True

        return False

    def check_time_limit(self, ticket: int, hours_limit: int = 4) -> bool:
        """
        Check if position has been open too long

        Args:
            ticket: Original position ticket
            hours_limit: Maximum hours before auto-close (default 4)

        Returns:
            bool: True if time limit exceeded
        """
        if ticket not in self.tracked_positions:
            return False

        position = self.tracked_positions[ticket]
        open_time = position.get('open_time')

        if open_time is None:
            return False

        # Calculate hours open
        time_open = datetime.now() - open_time
        hours_open = time_open.total_seconds() / 3600

        if hours_open >= hours_limit:
            print(f"⏰ Time limit reached for {ticket}")
            print(f"   Open for: {hours_open:.1f} hours")
            print(f"   Limit: {hours_limit} hours")
            print(f"   Auto-closing stuck position...")
            return True

        return False

    def check_partial_close_trigger(
        self,
        ticket: int,
        mt5_positions: List[Dict],
        account_balance: float,
        profit_target_percent: float,
        partial_close_config: Dict
    ) -> Optional[Dict]:
        """
        Check if we should execute a partial close at a profit milestone

        Args:
            ticket: Original position ticket
            mt5_positions: List of all current MT5 positions
            account_balance: Account balance
            profit_target_percent: Full profit target (e.g., 1.0%)
            partial_close_config: Dict with partial close settings

        Returns:
            Dict with partial close instructions or None
        """
        if not partial_close_config.get('enabled', False):
            return None

        if ticket not in self.tracked_positions:
            return None

        position = self.tracked_positions[ticket]
        partial_state = position['partial_close_state']

        # Calculate current profit
        net_profit = self.calculate_net_profit(ticket, mt5_positions)
        if net_profit is None or net_profit <= 0:
            return None

        # Calculate target profit in dollars
        full_target = account_balance * (profit_target_percent / 100.0)

        # Calculate profit percentage achieved
        profit_percent_achieved = (net_profit / full_target) * 100

        # Check partial close levels
        levels = partial_close_config.get('levels', [
            {'trigger_percent': 50, 'close_percent': 50},  # At 50% profit, close 50%
            {'trigger_percent': 75, 'close_percent': 30},  # At 75% profit, close 30%
        ])

        for level in levels:
            trigger = level['trigger_percent']
            close_pct = level['close_percent']

            # Check if this level has already been closed
            if trigger in partial_state['levels_closed']:
                continue

            # Check if we've reached this profit level
            if profit_percent_achieved >= trigger:
                print(f"📊 Partial close trigger reached for {ticket}")
                print(f"   Profit: ${net_profit:.2f} ({profit_percent_achieved:.1f}% of target)")
                print(f"   Closing {close_pct}% of position at {trigger}% profit level")

                return {
                    'ticket': ticket,
                    'trigger_percent': trigger,
                    'close_percent': close_pct,
                    'net_profit': net_profit,
                    'profit_percent_achieved': profit_percent_achieved,
                }

        return None

    def get_partial_close_tickets(
        self,
        ticket: int,
        close_percent: float,
        mt5_positions: List[Dict],
        close_order: str = 'recovery_first'
    ) -> List[Dict]:
        """
        Determine which positions to close for partial close

        Args:
            ticket: Original position ticket
            close_percent: Percentage of stack to close (0-100)
            mt5_positions: List of all current MT5 positions
            close_order: 'recovery_first', 'lifo', 'fifo', or 'largest_first'

        Returns:
            List of dicts with 'ticket', 'volume', and 'partial' keys
        """
        if ticket not in self.tracked_positions:
            return []

        position = self.tracked_positions[ticket]
        stack_tickets = self.get_all_stack_tickets(ticket)
        partial_state = position['partial_close_state']

        # Filter out already closed tickets
        available_tickets = [t for t in stack_tickets
                           if t not in partial_state['tickets_closed']]

        if not available_tickets:
            return []

        # Get position details from MT5
        stack_positions = []
        for mt5_pos in mt5_positions:
            if mt5_pos['ticket'] in available_tickets:
                stack_positions.append({
                    'ticket': mt5_pos['ticket'],
                    'volume': mt5_pos['volume'],
                    'type': mt5_pos['type'],
                    'is_original': mt5_pos['ticket'] == ticket,
                    'is_recovery': mt5_pos['ticket'] != ticket,
                    'timestamp': mt5_pos.get('time', 0),
                })

        if not stack_positions:
            return []

        # Calculate total volume
        total_volume = sum(p['volume'] for p in stack_positions)
        target_close_volume = total_volume * (close_percent / 100.0)

        # Sort positions based on close order strategy
        if close_order == 'recovery_first':
            # Close recovery positions first (grid, DCA, hedge), keep original last
            stack_positions.sort(key=lambda p: (not p['is_recovery'], p['timestamp']))

        elif close_order == 'lifo':
            # Close most recent first
            stack_positions.sort(key=lambda p: p['timestamp'], reverse=True)

        elif close_order == 'fifo':
            # Close oldest first
            stack_positions.sort(key=lambda p: p['timestamp'])

        elif close_order == 'largest_first':
            # Close largest positions first
            stack_positions.sort(key=lambda p: p['volume'], reverse=True)

        # Select positions to close until we reach target volume
        positions_to_close = []
        volume_accumulated = 0.0

        for pos in stack_positions:
            if volume_accumulated >= target_close_volume:
                break

            remaining_needed = target_close_volume - volume_accumulated

            if pos['volume'] <= remaining_needed:
                # Close entire position
                positions_to_close.append({
                    'ticket': pos['ticket'],
                    'volume': pos['volume'],  # Close full volume
                    'partial': False
                })
                volume_accumulated += pos['volume']
            else:
                # Close partial volume of this position - MUST ROUND TO BROKER STEP
                rounded_volume = round_volume_to_step(remaining_needed, step=0.01, min_lot=0.01)

                # Skip if rounded volume is invalid or too small
                if rounded_volume < 0.01 or rounded_volume > pos['volume']:
                    continue

                positions_to_close.append({
                    'ticket': pos['ticket'],
                    'volume': rounded_volume,  # Use rounded volume
                    'partial': True
                })
                volume_accumulated += rounded_volume
                break  # We've reached target

        return positions_to_close

    def record_partial_close(
        self,
        ticket: int,
        trigger_level: float,
        closed_tickets: List[int],
        closed_volume: float
    ):
        """
        Record that a partial close was executed

        Args:
            ticket: Original position ticket
            trigger_level: Which profit level triggered this close
            closed_tickets: List of tickets that were closed
            closed_volume: Total volume closed
        """
        if ticket not in self.tracked_positions:
            return

        position = self.tracked_positions[ticket]
        partial_state = position['partial_close_state']

        # Record this level as closed
        if trigger_level not in partial_state['levels_closed']:
            partial_state['levels_closed'].append(trigger_level)

        # Record closed tickets
        for closed_ticket in closed_tickets:
            if closed_ticket not in partial_state['tickets_closed']:
                partial_state['tickets_closed'].append(closed_ticket)

        # Update total closed volume
        partial_state['total_closed_volume'] += closed_volume
