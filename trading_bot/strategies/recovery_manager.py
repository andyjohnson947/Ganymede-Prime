"""
Recovery Strategy Manager
Implements Grid Trading, Hedging, and DCA/Martingale
All discovered from EA analysis of 428 trades
"""

from typing import Dict, List, Optional
from datetime import datetime

from utils.timezone_manager import get_current_time
from utils.logger import logger
from portfolio.instruments_config import get_recovery_settings, get_take_profit_settings
from config.strategy_config import (
    GRID_ENABLED,
    GRID_SPACING_PIPS,      # Fallback default
    MAX_GRID_LEVELS,        # Fallback default
    GRID_LOT_SIZE,
    HEDGE_ENABLED,
    HEDGE_TRIGGER_PIPS,     # Fallback default
    HEDGE_RATIO,
    MAX_HEDGES_PER_POSITION,
    STACK_DRAWDOWN_MULTIPLIER,  # Drawdown threshold for killing stacks
    DCA_ENABLED,
    DCA_TRIGGER_PIPS,       # Fallback default
    DCA_MAX_LEVELS,         # Fallback default
    DCA_MULTIPLIER,         # Fallback default
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

    def _get_recovery_settings(self, symbol: str) -> Dict:
        """
        Get recovery settings for a symbol with fallback to defaults.

        Args:
            symbol: Trading symbol

        Returns:
            Dictionary with recovery settings
        """
        try:
            # Try to get instrument-specific settings
            settings = get_recovery_settings(symbol)
            return settings
        except (KeyError, Exception):
            # Fallback to global defaults from strategy_config
            return {
                'grid_spacing_pips': GRID_SPACING_PIPS,
                'dca_trigger_pips': DCA_TRIGGER_PIPS,
                'hedge_trigger_pips': HEDGE_TRIGGER_PIPS,
                'dca_multiplier': DCA_MULTIPLIER,
                'max_grid_levels': MAX_GRID_LEVELS,
                'max_dca_levels': DCA_MAX_LEVELS,
            }

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

        Raises:
            ValueError: If invalid inputs provided
        """
        # Input validation
        if not isinstance(ticket, int) or ticket <= 0:
            raise ValueError(f"Invalid ticket: {ticket} (must be positive integer)")

        if not symbol or not isinstance(symbol, str):
            raise ValueError(f"Invalid symbol: {symbol} (must be non-empty string)")

        if position_type not in ('buy', 'sell'):
            raise ValueError(f"Invalid position_type: {position_type} (must be 'buy' or 'sell')")

        if entry_price <= 0:
            raise ValueError(f"Invalid entry_price: {entry_price} (must be positive)")

        if volume <= 0:
            raise ValueError(f"Invalid volume: {volume} (must be positive)")

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
            'open_time': get_current_time(),  # Track when position opened
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
        symbol = position['symbol']

        # Get instrument-specific recovery settings
        recovery_settings = self._get_recovery_settings(symbol)
        grid_spacing = recovery_settings['grid_spacing_pips']
        max_grid_levels = recovery_settings['max_grid_levels']

        # Check if maxed out grid levels
        if len(position['grid_levels']) >= max_grid_levels:
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
        expected_levels = int(pips_moved / grid_spacing) + 1

        # Need to add grid level?
        if expected_levels > len(position['grid_levels']) + 1:  # +1 for original position
            # Calculate grid price
            levels_added = len(position['grid_levels']) + 1
            grid_distance = grid_spacing * levels_added * pip_value

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
                'time': get_current_time()
            })

            position['total_volume'] += grid_volume
            position['recovery_active'] = True

            logger.info(f"🔹 Grid Level {len(position['grid_levels'])} triggered for {ticket}")
            logger.info(f"   Entry: {entry_price:.5f} → Grid: {grid_price:.5f}")
            logger.info(f"   Distance: {grid_spacing * levels_added:.1f} pips")

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
        symbol = position['symbol']

        # Get instrument-specific recovery settings
        recovery_settings = self._get_recovery_settings(symbol)
        hedge_trigger = recovery_settings['hedge_trigger_pips']

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
        if pips_underwater >= hedge_trigger:
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
                'time': get_current_time()
            })

            position['recovery_active'] = True

            logger.info(f"🛡️ Hedge activated for {ticket}")
            logger.info(f"   Original: {position_type.upper()} {position['initial_volume']:.2f} (total exposure: {position['total_volume']:.2f})")
            logger.info(f"   Hedge: {hedge_type.upper()} {hedge_volume:.2f} (ratio: {HEDGE_RATIO}x on initial)")
            logger.info(f"   Triggered at: {pips_underwater:.1f} pips underwater")

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
        symbol = position['symbol']

        # Get instrument-specific recovery settings
        recovery_settings = self._get_recovery_settings(symbol)
        dca_trigger = recovery_settings['dca_trigger_pips']
        dca_multiplier = recovery_settings['dca_multiplier']
        max_dca_levels = recovery_settings['max_dca_levels']

        # Check if maxed out DCA levels
        if max_dca_levels and len(position['dca_levels']) >= max_dca_levels:
            return None

        entry_price = position['entry_price']
        position_type = position['type']

        # Calculate pips moved
        if position_type == 'buy':
            pips_moved = (entry_price - current_price) / pip_value
        else:
            pips_moved = (current_price - entry_price) / pip_value

        # Check if underwater enough
        if pips_moved < dca_trigger:
            return None

        # Calculate expected DCA levels
        expected_levels = int(pips_moved / dca_trigger)

        # Need to add DCA level?
        if expected_levels > len(position['dca_levels']):
            # Calculate DCA volume (increase by multiplier)
            if len(position['dca_levels']) == 0:
                dca_volume = position['initial_volume'] * dca_multiplier
            else:
                last_dca = position['dca_levels'][-1]
                dca_volume = last_dca['volume'] * dca_multiplier

            # Round to broker step size (0.01)
            dca_volume = round_volume_to_step(dca_volume)

            # Add to tracked levels
            position['dca_levels'].append({
                'price': current_price,
                'volume': dca_volume,
                'level': len(position['dca_levels']) + 1,
                'time': get_current_time()
            })

            position['total_volume'] += dca_volume
            position['recovery_active'] = True

            logger.info(f"📊 DCA Level {len(position['dca_levels'])} triggered for {ticket}")
            logger.info(f"   Price: {current_price:.5f}")
            logger.info(f"   Volume: {dca_volume:.2f} (multiplier: {dca_multiplier}x)")
            logger.info(f"   Total volume now: {position['total_volume']:.2f}")

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
            logger.info(f"✅ Profit target reached for {ticket}")
            logger.info(f"   Net profit: ${net_profit:.2f}")
            logger.info(f"   Target: ${target_profit:.2f} ({profit_percent}% of ${account_balance:.2f})")
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
        time_open = get_current_time() - open_time
        hours_open = time_open.total_seconds() / 3600

        if hours_open >= hours_limit:
            logger.info(f"⏰ Time limit reached for {ticket}")
            logger.info(f"   Open for: {hours_open:.1f} hours")
            logger.info(f"   Limit: {hours_limit} hours")
            logger.info(f"   Auto-closing stuck position...")
            return True

        return False

    def check_stack_drawdown(
        self,
        ticket: int,
        mt5_positions: List[Dict],
        pip_value: float = 0.0001
    ) -> bool:
        """
        Check if recovery stack has exceeded drawdown threshold.
        Kills entire stack (original + grid + hedge + DCA) if net loss exceeds
        STACK_DRAWDOWN_MULTIPLIER × expected profit from original trade.

        Args:
            ticket: Original position ticket
            mt5_positions: List of all current MT5 positions
            pip_value: Pip value for symbol (0.0001 for most pairs, 0.01 for JPY)

        Returns:
            bool: True if stack should be closed due to excessive drawdown
        """
        if ticket not in self.tracked_positions:
            return False

        position = self.tracked_positions[ticket]
        symbol = position['symbol']
        initial_volume = position['initial_volume']

        # Calculate expected profit from original trade
        try:
            tp_settings = get_take_profit_settings(symbol)
            tp_pips = tp_settings['take_profit_pips']
        except (KeyError, Exception):
            # If no TP settings, can't calculate - skip check
            return False

        # Calculate expected profit in dollars
        # Formula: pips × pip_value × lot_size × 100,000 (standard lot)
        expected_profit = tp_pips * pip_value * initial_volume * 100000

        # Calculate drawdown threshold
        drawdown_threshold = -1 * (expected_profit * STACK_DRAWDOWN_MULTIPLIER)

        # Calculate current net P&L for entire stack
        net_profit = self.calculate_net_profit(ticket, mt5_positions)

        if net_profit is None:
            return False

        # Check if we've exceeded drawdown threshold (net profit is negative and below threshold)
        if net_profit <= drawdown_threshold:
            logger.info(f"🛑 STACK DRAWDOWN EXCEEDED for {ticket}")
            logger.info(f"   Symbol: {symbol}")
            logger.info(f"   Expected profit: ${expected_profit:.2f}")
            logger.info(f"   Drawdown threshold: ${drawdown_threshold:.2f} ({STACK_DRAWDOWN_MULTIPLIER}x)")
            logger.info(f"   Current stack P&L: ${net_profit:.2f}")
            logger.info(f"   ⚠️  Killing entire recovery stack to limit losses")
            return True

        return False

    def calculate_partial_close_volume(
        self,
        current_volume: float,
        close_percentage: float = 0.5,
        min_lot: float = 0.01,
        lot_step: float = 0.01
    ) -> float:
        """
        Calculate volume for partial close based on new lot size (0.04).

        Args:
            current_volume: Current position volume
            close_percentage: Percentage to close (0.0 to 1.0)
            min_lot: Minimum lot size allowed
            lot_step: Lot size step

        Returns:
            Volume to close (rounded to lot step)
        """
        close_volume = current_volume * close_percentage

        # Round to lot step
        close_volume = round_volume_to_step(
            close_volume,
            step=lot_step,
            min_lot=min_lot
        )

        # Ensure we're closing at least minimum lot
        if close_volume < min_lot:
            close_volume = min_lot

        # Ensure we don't close more than current volume
        if close_volume > current_volume:
            close_volume = current_volume

        return close_volume

    def get_recommended_partial_close(
        self,
        ticket: int,
        current_price: float,
        pip_value: float = 0.0001
    ) -> Optional[Dict]:
        """
        Get recommendation for partial close based on instrument-specific TP settings.

        Uses instrument-specific take profit levels instead of fixed dollar amounts.

        Args:
            ticket: Position ticket
            current_price: Current market price
            pip_value: Pip value for symbol (0.0001 for most pairs, 0.01 for JPY)

        Returns:
            Dictionary with partial close recommendation or None
        """
        if ticket not in self.tracked_positions:
            return None

        position = self.tracked_positions[ticket]
        symbol = position['symbol']
        entry_price = position['entry_price']
        position_type = position['type']
        total_volume = position['total_volume']

        # Get instrument-specific take profit settings
        try:
            tp_settings = get_take_profit_settings(symbol)
        except (KeyError, Exception):
            # Fallback to basic logic if no TP settings
            return None

        # Calculate pips in profit
        if position_type == 'buy':
            pips_profit = (current_price - entry_price) / pip_value
        else:
            pips_profit = (entry_price - current_price) / pip_value

        # Check if in profit
        if pips_profit <= 0:
            return None

        # Check TP levels and recommend partial closes
        partial_2_pips = tp_settings['partial_2_pips']
        partial_2_percent = tp_settings['partial_2_percent']
        partial_1_pips = tp_settings['partial_1_pips']
        partial_1_percent = tp_settings['partial_1_percent']
        full_tp_pips = tp_settings['full_tp_pips']

        # Determine recommended close based on instrument-specific TP levels
        if pips_profit >= full_tp_pips:
            # Full TP reached - close entire position
            recommended_volume = total_volume
            close_percent = 1.0
            reason = f"Full TP {full_tp_pips} pips reached - closing 100%"
        elif pips_profit >= partial_2_pips:
            # Second partial TP - close percentage from settings
            recommended_volume = self.calculate_partial_close_volume(total_volume, partial_2_percent)
            close_percent = partial_2_percent
            reason = f"Partial TP {partial_2_pips} pips reached - closing {int(partial_2_percent*100)}%"
        elif pips_profit >= partial_1_pips:
            # First partial TP - close percentage from settings
            recommended_volume = self.calculate_partial_close_volume(total_volume, partial_1_percent)
            close_percent = partial_1_percent
            reason = f"Partial TP {partial_1_pips} pips reached - closing {int(partial_1_percent*100)}%"
        else:
            # Not at any TP level yet
            return None

        return {
            'ticket': ticket,
            'symbol': symbol,
            'current_volume': total_volume,
            'close_volume': recommended_volume,
            'remaining_volume': total_volume - recommended_volume,
            'close_percentage': close_percent * 100,
            'pips_profit': pips_profit,
            'tp_level_hit': f"{pips_profit:.1f} pips",
            'reason': reason
        }

    def should_partial_close(
        self,
        ticket: int,
        current_profit: float,
        min_profit_for_partial: float = 5.0
    ) -> bool:
        """
        Determine if position should be partially closed.

        Args:
            ticket: Position ticket
            current_profit: Current profit in dollars
            min_profit_for_partial: Minimum profit to trigger partial close

        Returns:
            True if should partially close
        """
        if ticket not in self.tracked_positions:
            return False

        position = self.tracked_positions[ticket]

        # Only partial close if:
        # 1. Position is profitable above threshold
        # 2. Position has recovery levels active (want to reduce risk)
        # 3. Total volume is > 0.04 (enough to partially close)

        has_recovery = (
            len(position['grid_levels']) > 0 or
            len(position['hedge_tickets']) > 0 or
            len(position['dca_levels']) > 0
        )

        return (
            current_profit >= min_profit_for_partial and
            has_recovery and
            position['total_volume'] > 0.04
        )

