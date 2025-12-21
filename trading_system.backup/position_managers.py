"""
Position Management System
Grid, Hedge, and Recovery managers based on EA reverse engineering
"""

import trading_config as config
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta


class Position:
    """Represents a single trading position"""

    def __init__(self, ticket: int, symbol: str, position_type: str,
                 entry_price: float, lot_size: float, entry_time: datetime,
                 level_type: str = 'initial', level_number: int = 0,
                 hedge_pair_id: Optional[int] = None):
        self.ticket = ticket
        self.symbol = symbol
        self.type = position_type  # 'buy' or 'sell'
        self.entry_price = entry_price
        self.lot_size = lot_size
        self.entry_time = entry_time
        self.level_type = level_type  # 'initial', 'grid', 'hedge', 'recovery'
        self.level_number = level_number
        self.hedge_pair_id = hedge_pair_id  # Links hedge to original position
        self.exit_price = None
        self.exit_time = None
        self.profit = None
        self.is_open = True

    def close(self, exit_price: float, exit_time: datetime, profit: float):
        """Close the position"""
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.profit = profit
        self.is_open = False

    def get_pips_profit(self, current_price: float) -> float:
        """Calculate profit in pips"""
        if self.type == 'buy':
            pips = (current_price - self.entry_price) / config.POINT_VALUE
        else:  # sell
            pips = (self.entry_price - current_price) / config.POINT_VALUE
        return pips

    def __repr__(self):
        status = "OPEN" if self.is_open else f"CLOSED @ {self.exit_price}"
        return f"Position({self.ticket}, {self.type.upper()}, {self.lot_size}, @ {self.entry_price}, {status})"


class GridManager:
    """Manages grid trading positions"""

    def __init__(self):
        self.spacing_pips = config.GRID_SPACING_PIPS
        self.max_levels = config.MAX_GRID_LEVELS
        self.base_lot_size = config.GRID_BASE_LOT_SIZE

    def should_open_grid_level(self, positions: List[Position],
                                current_price: float, direction: str) -> bool:
        """
        Check if we should open next grid level

        Args:
            positions: Existing positions in same direction
            current_price: Current market price
            direction: 'buy' or 'sell'

        Returns:
            True if should open grid level
        """
        # Filter grid and initial positions only (not hedge or recovery)
        grid_positions = [p for p in positions
                         if p.type == direction and
                         p.level_type in ['initial', 'grid'] and
                         p.is_open]

        if len(grid_positions) >= self.max_levels:
            return False  # Max grid levels reached

        if not grid_positions:
            return False  # No initial position

        # Get last entry price
        last_entry = grid_positions[-1].entry_price

        # Calculate distance in pips
        if direction == 'buy':
            distance_pips = (last_entry - current_price) / config.POINT_VALUE
        else:  # sell
            distance_pips = (current_price - last_entry) / config.POINT_VALUE

        # Open grid if price moved required distance
        return distance_pips >= self.spacing_pips

    def get_grid_lot_size(self, level: int) -> float:
        """Get lot size for grid level (always fixed, normalized to broker requirements)"""
        return config.normalize_lot_size(self.base_lot_size)

    def calculate_average_entry(self, positions: List[Position]) -> float:
        """Calculate weighted average entry price"""
        if not positions:
            return 0.0

        total_lots = sum(p.lot_size for p in positions)
        weighted_sum = sum(p.entry_price * p.lot_size for p in positions)

        return weighted_sum / total_lots if total_lots > 0 else 0.0


class HedgeManager:
    """Manages hedge positions (2.4x overhedge) - tracks pairs for net P&L"""

    def __init__(self):
        self.hedge_ratio = config.HEDGE_RATIO
        self.trigger_pips = config.HEDGE_TRIGGER_PIPS
        self.time_window = timedelta(minutes=config.HEDGE_TIME_WINDOW_MINUTES)
        self.next_pair_id = 1  # Counter for hedge pair IDs

    def should_open_hedge(self, positions: List[Position],
                          current_price: float) -> Tuple[bool, Optional[str], float, Optional[int]]:
        """
        Check if we should open a hedge position

        Returns:
            (should_hedge, direction, lot_size, hedge_pair_id)
        """
        if not config.HEDGE_ENABLED:
            return False, None, 0.0, None

        # Get all non-hedge positions without existing pair
        non_hedge_positions = [p for p in positions
                              if p.level_type != 'hedge' and p.is_open and p.hedge_pair_id is None]

        if not non_hedge_positions:
            return False, None, 0.0, None

        # Calculate total exposure and average entry
        original_direction = non_hedge_positions[0].type
        total_lots = sum(p.lot_size for p in non_hedge_positions)
        avg_entry = sum(p.entry_price * p.lot_size for p in non_hedge_positions) / total_lots

        # Calculate pips underwater
        if original_direction == 'buy':
            pips_underwater = (avg_entry - current_price) / config.POINT_VALUE
        else:  # sell
            pips_underwater = (current_price - avg_entry) / config.POINT_VALUE

        # Trigger hedge if underwater beyond threshold
        if pips_underwater >= self.trigger_pips:
            hedge_direction = 'sell' if original_direction == 'buy' else 'buy'
            hedge_lot_size = config.normalize_lot_size(total_lots * self.hedge_ratio)

            # Assign pair ID and mark original positions
            pair_id = self.next_pair_id
            self.next_pair_id += 1

            # Mark all original positions with this pair ID
            for pos in non_hedge_positions:
                pos.hedge_pair_id = pair_id

            return True, hedge_direction, hedge_lot_size, pair_id

        return False, None, 0.0, None

    def get_hedge_pairs(self, positions: List[Position]) -> Dict[int, Dict[str, List[Position]]]:
        """
        Group positions by hedge_pair_id

        Returns:
            {pair_id: {'original': [positions], 'hedge': [positions]}}
        """
        pairs = {}

        for pos in positions:
            if pos.is_open and pos.hedge_pair_id is not None:
                if pos.hedge_pair_id not in pairs:
                    pairs[pos.hedge_pair_id] = {'original': [], 'hedge': []}

                if pos.level_type == 'hedge':
                    pairs[pos.hedge_pair_id]['hedge'].append(pos)
                else:
                    pairs[pos.hedge_pair_id]['original'].append(pos)

        return pairs

    def calculate_pair_net_pnl(self, original_positions: List[Position],
                               hedge_positions: List[Position],
                               current_price: float) -> Tuple[float, float, float]:
        """
        Calculate net P&L for a hedge pair

        Returns:
            (net_pnl_pips, original_pnl_pips, hedge_pnl_pips)
        """
        original_pnl = sum(p.get_pips_profit(current_price) * p.lot_size
                          for p in original_positions)
        hedge_pnl = sum(p.get_pips_profit(current_price) * p.lot_size
                       for p in hedge_positions)

        return original_pnl + hedge_pnl, original_pnl, hedge_pnl

    def should_close_hedge_pair(self, original_positions: List[Position],
                                hedge_positions: List[Position],
                                current_price: float,
                                use_advanced_exit: bool = True) -> Tuple[bool, bool, str]:
        """
        Determine if hedge pair should be closed (matching original EA logic)

        Args:
            original_positions: Original direction positions
            hedge_positions: Hedge positions
            current_price: Current market price
            use_advanced_exit: If True, close losing hedge when original is profitable

        Returns:
            (close_both, close_hedge_only, reason)
        """
        if not original_positions or not hedge_positions:
            # Orphaned positions - close whatever remains
            return True, False, "Orphaned hedge pair"

        net_pnl, original_pnl, hedge_pnl = self.calculate_pair_net_pnl(
            original_positions, hedge_positions, current_price
        )

        # ORIGINAL EA LOGIC: Close both when net profitable
        if net_pnl > 0:
            return True, False, f"Net profit achieved: {net_pnl:.1f} pips"

        # ADVANCED LOGIC: Close losing hedge if original direction proves correct
        if use_advanced_exit:
            # If original positions profitable AND hedge losing
            if original_pnl > 0 and hedge_pnl < 0:
                # Original direction was correct, close the losing hedge
                # Keep original positions to capture more profit
                return False, True, f"Original profitable ({original_pnl:.1f} pips), closing losing hedge"

        return False, False, "Pair still underwater"


class RecoveryManager:
    """Manages martingale recovery positions (limited to 5 levels)"""

    def __init__(self):
        self.max_recovery_levels = config.MAX_RECOVERY_LEVELS
        self.multiplier = config.MARTINGALE_MULTIPLIER
        self.max_total_levels = config.MAX_TOTAL_LEVELS

    def should_start_recovery(self, positions: List[Position],
                              current_price: float) -> bool:
        """Check if recovery mode should start (grid exhausted)"""
        if not config.RECOVERY_ENABLED:
            return False

        # Count grid positions
        grid_positions = [p for p in positions
                         if p.level_type in ['initial', 'grid'] and p.is_open]

        # Start recovery if grid is maxed out and still losing
        if len(grid_positions) >= config.MAX_GRID_LEVELS:
            # Calculate if we're still underwater
            if grid_positions:
                direction = grid_positions[0].type
                avg_entry = sum(p.entry_price * p.lot_size for p in grid_positions) / \
                           sum(p.lot_size for p in grid_positions)

                if direction == 'buy':
                    pips_underwater = (avg_entry - current_price) / config.POINT_VALUE
                else:
                    pips_underwater = (current_price - avg_entry) / config.POINT_VALUE

                return pips_underwater > config.GRID_SPACING_PIPS

        return False

    def get_recovery_lot_size(self, positions: List[Position],
                              recovery_level: int) -> Optional[float]:
        """
        Calculate lot size for recovery level with broker normalization

        Args:
            positions: All positions
            recovery_level: Recovery level number (1-5)

        Returns:
            Lot size or None if max levels reached
        """
        if recovery_level > self.max_recovery_levels:
            return None  # Max recovery levels reached

        # Get total current levels
        total_levels = len([p for p in positions if p.is_open])
        if total_levels >= self.max_total_levels:
            return None  # Absolute max reached

        # Calculate martingale lot size
        base_lot = config.GRID_BASE_LOT_SIZE
        lot_size = base_lot * (self.multiplier ** recovery_level)

        # Normalize to broker requirements (fixes invalid volume errors)
        return config.normalize_lot_size(lot_size)

    def should_open_recovery_level(self, positions: List[Position],
                                   current_price: float, direction: str) -> Tuple[bool, Optional[float]]:
        """
        Check if we should open next recovery level

        Returns:
            (should_open, lot_size)
        """
        if not config.RECOVERY_ENABLED:
            return False, None

        # Get all recovery positions
        recovery_positions = [p for p in positions
                            if p.level_type == 'recovery' and
                            p.type == direction and
                            p.is_open]

        recovery_level = len(recovery_positions) + 1

        if recovery_level > self.max_recovery_levels:
            return False, None  # Max recovery reached

        # Check if we should start or continue recovery
        if recovery_level == 1:
            # First recovery level - check if grid exhausted
            if not self.should_start_recovery(positions, current_price):
                return False, None
        else:
            # Subsequent recovery levels - check spacing
            last_recovery = recovery_positions[-1]
            if direction == 'buy':
                distance_pips = (last_recovery.entry_price - current_price) / config.POINT_VALUE
            else:
                distance_pips = (current_price - last_recovery.entry_price) / config.POINT_VALUE

            if distance_pips < config.GRID_SPACING_PIPS:
                return False, None  # Not far enough yet

        # Calculate lot size for this recovery level
        lot_size = self.get_recovery_lot_size(positions, recovery_level)

        if lot_size is None:
            return False, None

        return True, lot_size
