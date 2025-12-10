"""
DCA Position Manager
Manages multiple DCA positions and execution
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd

from .dca_strategy import DCAStrategy, DCAPosition, DCAConfig, DCAEntry, DCADirection


class DCAPositionManager:
    """Manages DCA positions across multiple symbols"""

    def __init__(self):
        """Initialize DCA Position Manager"""
        self.logger = logging.getLogger(__name__)
        self.positions: Dict[str, DCAPosition] = {}  # symbol -> position
        self.strategies: Dict[str, DCAStrategy] = {}  # symbol -> strategy
        self.closed_positions: List[DCAPosition] = []

    def create_position(
        self,
        config: DCAConfig,
        initial_price: float,
        timestamp: datetime
    ) -> DCAPosition:
        """
        Create a new DCA position

        Args:
            config: DCA configuration
            initial_price: Initial entry price
            timestamp: Opening timestamp

        Returns:
            New DCAPosition object
        """
        symbol = config.symbol

        if symbol in self.positions:
            self.logger.warning(f"Position already exists for {symbol}")
            return self.positions[symbol]

        # Create position
        position = DCAPosition(
            symbol=symbol,
            direction=config.direction,
            config=config,
            opened_at=timestamp
        )

        # Create strategy
        strategy = DCAStrategy(config)

        # Create initial entry
        initial_entry = strategy.create_entry(
            position=position,
            price=initial_price,
            timestamp=timestamp,
            reason="Initial entry"
        )

        position.entries.append(initial_entry)

        # Store
        self.positions[symbol] = position
        self.strategies[symbol] = strategy

        self.logger.info(f"Created DCA position for {symbol}: {config.direction.value} @ {initial_price}")
        return position

    def update_position(
        self,
        symbol: str,
        current_price: float,
        current_time: datetime,
        indicators: Dict = None
    ) -> Optional[DCAEntry]:
        """
        Update a DCA position (check if new entry needed)

        Args:
            symbol: Trading symbol
            current_price: Current market price
            current_time: Current timestamp
            indicators: Dictionary of indicator values

        Returns:
            New DCAEntry if added, None otherwise
        """
        if symbol not in self.positions:
            self.logger.warning(f"No position found for {symbol}")
            return None

        position = self.positions[symbol]
        strategy = self.strategies[symbol]

        if not position.is_active:
            return None

        # Check if we should add entry
        if strategy.should_add_entry(position, current_price, current_time, indicators):
            # Create new entry
            entry = strategy.create_entry(
                position=position,
                price=current_price,
                timestamp=current_time,
                reason="DCA entry"
            )

            position.entries.append(entry)
            self.logger.info(f"Added DCA entry for {symbol}: #{entry.entry_id} @ {current_price}")
            return entry

        # Update unrealized PnL
        position.unrealized_pnl = position.calculate_pnl(current_price)

        # Check if should close
        should_close, reason = strategy.should_close_position(position, current_price)
        if should_close:
            self.close_position(symbol, current_price, current_time, reason)

        return None

    def close_position(
        self,
        symbol: str,
        closing_price: float,
        timestamp: datetime,
        reason: str = "Manual close"
    ):
        """
        Close a DCA position

        Args:
            symbol: Trading symbol
            closing_price: Closing price
            timestamp: Closing timestamp
            reason: Reason for closing
        """
        if symbol not in self.positions:
            self.logger.warning(f"No position found for {symbol}")
            return

        position = self.positions[symbol]

        if not position.is_active:
            self.logger.warning(f"Position for {symbol} already closed")
            return

        # Calculate final PnL
        final_pnl = position.calculate_pnl(closing_price)
        position.realized_pnl = final_pnl
        position.unrealized_pnl = 0.0

        # Update position state
        position.is_active = False
        position.closed_at = timestamp

        # Move to closed positions
        self.closed_positions.append(position)
        del self.positions[symbol]
        del self.strategies[symbol]

        self.logger.info(
            f"Closed DCA position for {symbol}: "
            f"PnL: {final_pnl:.2f} ({position.calculate_pnl_percent(closing_price):.2f}%) "
            f"Reason: {reason}"
        )

    def get_position(self, symbol: str) -> Optional[DCAPosition]:
        """
        Get position for symbol

        Args:
            symbol: Trading symbol

        Returns:
            DCAPosition if exists, None otherwise
        """
        return self.positions.get(symbol)

    def get_all_positions(self) -> Dict[str, DCAPosition]:
        """
        Get all active positions

        Returns:
            Dictionary of symbol -> position
        """
        return self.positions.copy()

    def get_position_summary(self, symbol: str, current_price: float) -> Optional[Dict]:
        """
        Get summary for a specific position

        Args:
            symbol: Trading symbol
            current_price: Current market price

        Returns:
            Position summary dictionary
        """
        if symbol not in self.positions:
            return None

        position = self.positions[symbol]
        strategy = self.strategies[symbol]

        return strategy.get_summary(position, current_price)

    def get_all_summaries(self, prices: Dict[str, float]) -> List[Dict]:
        """
        Get summaries for all positions

        Args:
            prices: Dictionary of symbol -> current price

        Returns:
            List of position summaries
        """
        summaries = []

        for symbol, position in self.positions.items():
            current_price = prices.get(symbol)
            if current_price:
                strategy = self.strategies[symbol]
                summary = strategy.get_summary(position, current_price)
                summaries.append(summary)

        return summaries

    def get_portfolio_summary(self, prices: Dict[str, float]) -> Dict:
        """
        Get overall portfolio summary

        Args:
            prices: Dictionary of symbol -> current price

        Returns:
            Portfolio summary dictionary
        """
        total_pnl = 0.0
        total_cost = 0.0
        num_positions = len(self.positions)

        for symbol, position in self.positions.items():
            current_price = prices.get(symbol)
            if current_price:
                total_pnl += position.calculate_pnl(current_price)
                total_cost += position.total_cost

        total_pnl_percent = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0

        # Include closed positions
        realized_pnl = sum(pos.realized_pnl for pos in self.closed_positions)

        return {
            'num_active_positions': num_positions,
            'num_closed_positions': len(self.closed_positions),
            'total_unrealized_pnl': total_pnl,
            'total_unrealized_pnl_percent': total_pnl_percent,
            'total_realized_pnl': realized_pnl,
            'total_pnl': total_pnl + realized_pnl,
            'total_cost': total_cost
        }

    def get_performance_stats(self) -> Dict:
        """
        Get performance statistics for closed positions

        Returns:
            Statistics dictionary
        """
        if not self.closed_positions:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'total_pnl': 0.0
            }

        pnls = [pos.realized_pnl for pos in self.closed_positions]
        wins = [pnl for pnl in pnls if pnl > 0]
        losses = [pnl for pnl in pnls if pnl < 0]

        return {
            'total_trades': len(pnls),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': len(wins) / len(pnls) * 100 if pnls else 0.0,
            'avg_win': sum(wins) / len(wins) if wins else 0.0,
            'avg_loss': sum(losses) / len(losses) if losses else 0.0,
            'total_pnl': sum(pnls),
            'largest_win': max(wins) if wins else 0.0,
            'largest_loss': min(losses) if losses else 0.0
        }

    def clear_closed_positions(self):
        """Clear the list of closed positions"""
        self.closed_positions.clear()
        self.logger.info("Cleared closed positions history")
