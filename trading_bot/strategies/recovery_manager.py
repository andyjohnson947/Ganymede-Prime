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
        volume: float
    ):
        """
        Start tracking a position for recovery

        Args:
            ticket: Position ticket
            symbol: Trading symbol
            entry_price: Entry price
            position_type: 'buy' or 'sell'
            volume: Initial lot size
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
            'partial_close_state': {  # Track partial closures
                'levels_closed': [],  # Which profit levels have been closed
                'tickets_closed': [],  # Which tickets have been closed
                'total_closed_volume': 0.0,  # Total volume closed via partial
            },
        }

    def untrack_position(self, ticket: int):
        """Remove position from tracking"""
        if ticket in self.tracked_positions:
            del self.tracked_positions[ticket]

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

        # 🔍 DIAGNOSTIC LOGGING
        print(f"\n[GRID DIAGNOSTIC] Ticket: {ticket}")
        print(f"  Entry: {entry_price:.5f} | Current: {current_price:.5f}")
        print(f"  Pip value: {pip_value}")
        print(f"  Price diff: {abs(current_price - entry_price):.5f}")
        print(f"  Pips moved: {pips_moved:.2f}")
        print(f"  Grid spacing: {GRID_SPACING_PIPS} pips")
        print(f"  Current grid levels: {len(position['grid_levels'])}")

        # Check if underwater
        if pips_moved <= 0:
            print(f"  ⏸️  Not underwater - no grid needed")
            return None

        # Calculate expected grid levels
        expected_levels = int(pips_moved / GRID_SPACING_PIPS) + 1

        print(f"  Expected grid levels: {expected_levels}")
        print(f"  Condition: {expected_levels} > {len(position['grid_levels'])} + 1 = {expected_levels > len(position['grid_levels']) + 1}")

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
                'comment': f'Grid L{len(position["grid_levels"])} - {ticket}'
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

        # 🔍 DIAGNOSTIC LOGGING
        print(f"\n[HEDGE DIAGNOSTIC] Ticket: {ticket}")
        print(f"  Entry: {entry_price:.5f} | Current: {current_price:.5f}")
        print(f"  Pip value: {pip_value}")
        print(f"  Price diff: {abs(current_price - entry_price):.5f}")
        print(f"  Pips underwater: {pips_underwater:.2f}")
        print(f"  Hedge trigger: {HEDGE_TRIGGER_PIPS} pips")
        print(f"  Current hedges: {len(position['hedge_tickets'])}/{MAX_HEDGES_PER_POSITION}")
        print(f"  Condition: {pips_underwater:.2f} >= {HEDGE_TRIGGER_PIPS} = {pips_underwater >= HEDGE_TRIGGER_PIPS}")

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
                'comment': f'Hedge - {ticket}'
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

            # Add to tracked levels
            position['dca_levels'].append({
                'price': current_price,
                'volume': dca_volume,
                'level': len(position['dca_levels']) + 1,
                'time': datetime.now()
            })

            position['total_volume'] += dca_volume
            position['recovery_active'] = True

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
                'comment': f'DCA L{len(position["dca_levels"])} - {ticket}'
            }

        return None

    def check_all_recovery_triggers(
        self,
        ticket: int,
        current_price: float,
        pip_value: float = 0.0001
    ) -> List[Dict]:
        """
        Check all recovery mechanisms at once

        Args:
            ticket: Position ticket
            current_price: Current price
            pip_value: Pip value for symbol

        Returns:
            List of recovery actions to take
        """
        actions = []

        # Check grid
        grid_action = self.check_grid_trigger(ticket, current_price, pip_value)
        if grid_action:
            actions.append(grid_action)

        # Check hedge
        hedge_action = self.check_hedge_trigger(ticket, current_price, pip_value)
        if hedge_action:
            actions.append(hedge_action)

        # Check DCA
        dca_action = self.check_dca_trigger(ticket, current_price, pip_value)
        if dca_action:
            actions.append(dca_action)

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
    ) -> List[int]:
        """
        Determine which positions to close for partial close

        Args:
            ticket: Original position ticket
            close_percent: Percentage of stack to close (0-100)
            mt5_positions: List of all current MT5 positions
            close_order: 'recovery_first', 'lifo', 'fifo', or 'largest_first'

        Returns:
            List of ticket numbers to close
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
        tickets_to_close = []
        volume_to_close = 0.0

        for pos in stack_positions:
            if volume_to_close >= target_close_volume:
                break

            tickets_to_close.append(pos['ticket'])
            volume_to_close += pos['volume']

        return tickets_to_close

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
