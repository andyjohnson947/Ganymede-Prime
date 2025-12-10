"""
DCA Strategy Implementation
Handles dollar cost averaging logic and calculations
"""

import pandas as pd
import numpy as np
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from enum import Enum


class DCAType(Enum):
    """Types of DCA strategies"""
    FIXED_AMOUNT = "fixed_amount"  # Fixed dollar amount per entry
    FIXED_SIZE = "fixed_size"  # Fixed position size per entry
    GRID = "grid"  # Grid-based entries at price levels
    SIGNAL_BASED = "signal_based"  # Based on indicators/patterns
    TIME_BASED = "time_based"  # Regular time intervals


class DCADirection(Enum):
    """Direction for DCA"""
    LONG = "long"
    SHORT = "short"


@dataclass
class DCAConfig:
    """Configuration for DCA strategy"""
    symbol: str
    direction: DCADirection
    dca_type: DCAType

    # Entry parameters
    initial_size: float  # Initial position size
    dca_size: float  # Size for each DCA entry
    max_entries: int = 5  # Maximum number of DCA entries

    # Fixed amount DCA
    fixed_amount: float = 1000.0  # Fixed dollar amount per entry

    # Grid DCA
    grid_spacing_percent: float = 1.0  # Spacing between grid levels (%)
    grid_start_price: Optional[float] = None  # Starting price for grid

    # Time-based DCA
    time_interval_hours: int = 24  # Hours between DCA entries

    # Signal-based DCA
    signal_threshold: float = 0.7  # Confidence threshold for signals

    # Risk management
    max_total_size: float = 10.0  # Maximum total position size
    stop_loss_percent: float = 10.0  # Stop loss percentage
    take_profit_percent: float = 20.0  # Take profit percentage

    # Averaging down
    allow_averaging_down: bool = True
    max_drawdown_for_dca: float = 5.0  # Max drawdown % before stopping DCA

    # Dynamic sizing
    use_dynamic_sizing: bool = False
    size_multiplier: float = 1.5  # Multiplier for each DCA entry (pyramid/martingale)


@dataclass
class DCAEntry:
    """Represents a single DCA entry"""
    entry_id: int
    timestamp: datetime
    price: float
    size: float
    cost: float
    reason: str  # Why this entry was made


@dataclass
class DCAPosition:
    """Represents a complete DCA position"""
    symbol: str
    direction: DCADirection
    entries: List[DCAEntry] = field(default_factory=list)
    config: Optional[DCAConfig] = None

    # Position state
    is_active: bool = True
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    # Performance
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    @property
    def total_size(self) -> float:
        """Total position size"""
        return sum(entry.size for entry in self.entries)

    @property
    def total_cost(self) -> float:
        """Total cost of position"""
        return sum(entry.cost for entry in self.entries)

    @property
    def average_price(self) -> float:
        """Average entry price"""
        if self.total_size == 0:
            return 0.0
        return self.total_cost / self.total_size

    @property
    def num_entries(self) -> int:
        """Number of entries"""
        return len(self.entries)

    def calculate_pnl(self, current_price: float) -> float:
        """Calculate unrealized PnL"""
        if self.total_size == 0:
            return 0.0

        if self.direction == DCADirection.LONG:
            pnl = (current_price - self.average_price) * self.total_size
        else:  # SHORT
            pnl = (self.average_price - current_price) * self.total_size

        return pnl

    def calculate_pnl_percent(self, current_price: float) -> float:
        """Calculate unrealized PnL as percentage"""
        if self.total_cost == 0:
            return 0.0

        pnl = self.calculate_pnl(current_price)
        return (pnl / self.total_cost) * 100


class DCAStrategy:
    """Implements dollar cost averaging strategies"""

    def __init__(self, config: DCAConfig):
        """
        Initialize DCA Strategy

        Args:
            config: DCA configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Track grid levels if using grid DCA
        self.grid_levels: List[float] = []
        if config.dca_type == DCAType.GRID:
            self._initialize_grid_levels()

    def _initialize_grid_levels(self):
        """Initialize grid levels for grid-based DCA"""
        if self.config.grid_start_price is None:
            self.logger.warning("Grid start price not set")
            return

        start_price = self.config.grid_start_price
        spacing = self.config.grid_spacing_percent / 100.0

        # Generate grid levels
        for i in range(self.config.max_entries):
            if self.config.direction == DCADirection.LONG:
                # For long positions, grid levels go down from start price
                level = start_price * (1 - spacing * i)
            else:
                # For short positions, grid levels go up from start price
                level = start_price * (1 + spacing * i)

            self.grid_levels.append(level)

        self.logger.info(f"Initialized {len(self.grid_levels)} grid levels: {self.grid_levels}")

    def should_open_position(
        self,
        current_price: float,
        indicators: Dict = None,
        pattern_signals: List = None
    ) -> bool:
        """
        Determine if we should open a new DCA position

        Args:
            current_price: Current market price
            indicators: Dictionary of indicator values
            pattern_signals: List of detected patterns

        Returns:
            True if should open position
        """
        if self.config.dca_type == DCAType.SIGNAL_BASED:
            # Check if we have strong enough signals
            if pattern_signals:
                for pattern in pattern_signals:
                    if pattern.get('confidence', 0) >= self.config.signal_threshold:
                        # Check if direction matches
                        pattern_direction = pattern.get('direction', '')
                        if (self.config.direction == DCADirection.LONG and pattern_direction == 'bullish') or \
                           (self.config.direction == DCADirection.SHORT and pattern_direction == 'bearish'):
                            return True
            return False

        # For other types, default to opening position
        return True

    def should_add_entry(
        self,
        position: DCAPosition,
        current_price: float,
        current_time: datetime,
        indicators: Dict = None
    ) -> bool:
        """
        Determine if we should add another DCA entry

        Args:
            position: Current DCA position
            current_price: Current market price
            current_time: Current timestamp
            indicators: Dictionary of indicator values

        Returns:
            True if should add entry
        """
        # Check if max entries reached
        if position.num_entries >= self.config.max_entries:
            self.logger.debug(f"Max entries ({self.config.max_entries}) reached")
            return False

        # Check if max total size reached
        if position.total_size >= self.config.max_total_size:
            self.logger.debug(f"Max total size ({self.config.max_total_size}) reached")
            return False

        # Check drawdown limit
        if not self.config.allow_averaging_down:
            pnl_percent = position.calculate_pnl_percent(current_price)
            if pnl_percent < -self.config.max_drawdown_for_dca:
                self.logger.debug(f"Max drawdown for DCA ({self.config.max_drawdown_for_dca}%) exceeded")
                return False

        # Strategy-specific logic
        if self.config.dca_type == DCAType.FIXED_AMOUNT or self.config.dca_type == DCAType.FIXED_SIZE:
            # Check if price has moved enough to justify new entry
            price_change_percent = abs((current_price - position.average_price) / position.average_price) * 100

            if self.config.direction == DCADirection.LONG:
                # For long, add when price drops
                if current_price < position.average_price and price_change_percent >= 1.0:
                    return True
            else:
                # For short, add when price rises
                if current_price > position.average_price and price_change_percent >= 1.0:
                    return True

        elif self.config.dca_type == DCAType.GRID:
            # Check if price has hit a grid level
            for level in self.grid_levels:
                if not self._is_level_filled(position, level):
                    if self._is_price_at_level(current_price, level):
                        return True

        elif self.config.dca_type == DCAType.TIME_BASED:
            # Check if enough time has passed since last entry
            if position.entries:
                last_entry = position.entries[-1]
                time_since_last = (current_time - last_entry.timestamp).total_seconds() / 3600
                if time_since_last >= self.config.time_interval_hours:
                    return True
            else:
                return True  # First entry

        return False

    def calculate_entry_size(self, position: DCAPosition, current_price: float) -> float:
        """
        Calculate size for next DCA entry

        Args:
            position: Current DCA position
            current_price: Current market price

        Returns:
            Size for next entry
        """
        if self.config.dca_type == DCAType.FIXED_AMOUNT:
            # Fixed dollar amount
            return self.config.fixed_amount / current_price

        elif self.config.dca_type == DCAType.FIXED_SIZE:
            # Fixed position size
            if self.config.use_dynamic_sizing and position.num_entries > 0:
                # Apply multiplier for pyramiding/martingale
                multiplier = self.config.size_multiplier ** position.num_entries
                return self.config.dca_size * multiplier
            return self.config.dca_size

        elif self.config.dca_type == DCAType.GRID:
            # Grid-based sizing
            return self.config.dca_size

        elif self.config.dca_type == DCAType.TIME_BASED:
            # Time-based sizing
            return self.config.dca_size

        else:
            return self.config.dca_size

    def create_entry(
        self,
        position: DCAPosition,
        price: float,
        timestamp: datetime,
        reason: str = "DCA"
    ) -> DCAEntry:
        """
        Create a new DCA entry

        Args:
            position: Current DCA position
            price: Entry price
            timestamp: Entry timestamp
            reason: Reason for entry

        Returns:
            New DCAEntry object
        """
        size = self.calculate_entry_size(position, price)

        # Ensure we don't exceed max total size
        if position.total_size + size > self.config.max_total_size:
            size = self.config.max_total_size - position.total_size

        cost = size * price
        entry_id = position.num_entries + 1

        entry = DCAEntry(
            entry_id=entry_id,
            timestamp=timestamp,
            price=price,
            size=size,
            cost=cost,
            reason=reason
        )

        self.logger.info(f"Created DCA entry #{entry_id}: {size:.4f} @ {price:.5f} (cost: {cost:.2f})")
        return entry

    def should_close_position(
        self,
        position: DCAPosition,
        current_price: float
    ) -> tuple[bool, str]:
        """
        Determine if we should close the position

        Args:
            position: Current DCA position
            current_price: Current market price

        Returns:
            Tuple of (should_close, reason)
        """
        if position.total_size == 0:
            return False, ""

        pnl_percent = position.calculate_pnl_percent(current_price)

        # Check stop loss
        if pnl_percent <= -self.config.stop_loss_percent:
            return True, f"Stop loss hit ({pnl_percent:.2f}%)"

        # Check take profit
        if pnl_percent >= self.config.take_profit_percent:
            return True, f"Take profit hit ({pnl_percent:.2f}%)"

        return False, ""

    def _is_level_filled(self, position: DCAPosition, level: float) -> bool:
        """Check if a grid level has been filled"""
        tolerance = 0.0001  # Price tolerance
        for entry in position.entries:
            if abs(entry.price - level) / level < tolerance:
                return True
        return False

    def _is_price_at_level(self, current_price: float, level: float) -> bool:
        """Check if current price is at a grid level"""
        tolerance = 0.002  # 0.2% tolerance
        return abs(current_price - level) / level < tolerance

    def get_summary(self, position: DCAPosition, current_price: float) -> Dict:
        """
        Get summary of DCA position

        Args:
            position: DCA position
            current_price: Current market price

        Returns:
            Dictionary with position summary
        """
        return {
            'symbol': position.symbol,
            'direction': position.direction.value,
            'num_entries': position.num_entries,
            'total_size': position.total_size,
            'total_cost': position.total_cost,
            'average_price': position.average_price,
            'current_price': current_price,
            'unrealized_pnl': position.calculate_pnl(current_price),
            'unrealized_pnl_percent': position.calculate_pnl_percent(current_price),
            'realized_pnl': position.realized_pnl,
            'is_active': position.is_active,
            'opened_at': position.opened_at,
            'entries': [
                {
                    'id': e.entry_id,
                    'price': e.price,
                    'size': e.size,
                    'cost': e.cost,
                    'timestamp': e.timestamp,
                    'reason': e.reason
                }
                for e in position.entries
            ]
        }
