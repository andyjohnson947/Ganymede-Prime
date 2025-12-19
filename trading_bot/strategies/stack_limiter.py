"""
Stack Drawdown Limiter - Monitors and enforces per-stack loss limits

Key features:
- Dynamic limit based on 3x initial stake (position size)
- Tracks recovery effectiveness (is loss decreasing?)
- Auto-closes if stack exceeds 3x initial stake loss
- Prevents catastrophic margin exhaustion
"""

from typing import Dict, List, Optional
from datetime import datetime


class StackDrawdownLimiter:
    """Enforces per-stack drawdown limits with recovery-aware logic"""

    def __init__(self, stake_multiplier: float = 3.0):
        """
        Initialize stack limiter

        Args:
            stake_multiplier: Loss limit as multiple of initial stake (default 3.0x)
        """
        self.stake_multiplier = stake_multiplier
        # Reference value: $10,000 per 1.0 lot for calculating stake
        # So 0.08 lots = $800 stake, 0.12 lots = $1200 stake, etc.
        self.reference_value_per_lot = 10000.0

        # Track stack health
        self.stack_max_drawdown = {}  # ticket -> max loss seen
        self.stack_recovery_active = {}  # ticket -> bool (has recovery been triggered?)
        self.stack_last_check = {}  # ticket -> timestamp
        self.stack_initial_volume = {}  # ticket -> initial lot size
        self.stack_max_loss_limit = {}  # ticket -> calculated max loss limit

    def check_stack_limit(
        self,
        ticket: int,
        current_drawdown: float,
        recovery_active: bool,
        symbol: str,
        initial_volume: float = None
    ) -> Dict:
        """
        Check if stack has exceeded drawdown limit (3x initial stake)

        Logic:
        1. Calculate stake = initial_volume * $10,000 per lot
        2. Max loss = 3x stake (e.g., 0.08 lots = $800 stake → $2,400 max loss)
        3. Warning zone at 80% of limit (allows recovery room to work)
        4. Auto-close at 100% of limit (3x stake)

        Args:
            ticket: Parent position ticket
            current_drawdown: Current stack P&L (negative = loss)
            recovery_active: Whether recovery mechanisms are active
            symbol: Trading symbol
            initial_volume: Initial position size in lots (required for first check)

        Returns:
            Dict with status and action to take
        """
        # Convert P&L to absolute loss
        current_loss = abs(current_drawdown) if current_drawdown < 0 else 0.0

        # Calculate or retrieve max loss limit for this stack
        if ticket not in self.stack_max_loss_limit:
            if initial_volume is None:
                # Can't calculate limit without initial volume
                return {
                    'status': 'error',
                    'action': 'continue',
                    'message': 'Missing initial_volume - cannot calculate limit'
                }

            # Calculate stake and max loss limit
            stake = initial_volume * self.reference_value_per_lot
            max_loss_limit = stake * self.stake_multiplier

            # Store for future checks
            self.stack_initial_volume[ticket] = initial_volume
            self.stack_max_loss_limit[ticket] = max_loss_limit
        else:
            max_loss_limit = self.stack_max_loss_limit[ticket]

        # Calculate warning threshold (80% of max limit)
        warning_threshold = max_loss_limit * 0.80

        # Track maximum loss for this stack
        if ticket not in self.stack_max_drawdown:
            self.stack_max_drawdown[ticket] = current_loss
        else:
            self.stack_max_drawdown[ticket] = max(self.stack_max_drawdown[ticket], current_loss)

        # Track recovery state
        if recovery_active and ticket not in self.stack_recovery_active:
            self.stack_recovery_active[ticket] = True

        max_loss = self.stack_max_drawdown[ticket]
        is_improving = current_loss < max_loss  # Loss is decreasing = recovery working

        # Decision matrix
        if current_loss < warning_threshold:
            # SAFE: Under 80% of limit
            return {
                'status': 'safe',
                'action': 'continue',
                'current_loss': current_loss,
                'limit': max_loss_limit,
                'warning_threshold': warning_threshold,
                'message': f'Stack loss ${current_loss:.2f} within limit ${max_loss_limit:.2f} ({self.stake_multiplier}x stake)'
            }

        elif current_loss < max_loss_limit:
            # WARNING ZONE: 80%-100% of limit
            if recovery_active and is_improving:
                # Recovery is active AND working (loss decreasing)
                return {
                    'status': 'warning_recovery_working',
                    'action': 'monitor',
                    'current_loss': current_loss,
                    'max_loss': max_loss,
                    'limit': max_loss_limit,
                    'message': f'Stack loss ${current_loss:.2f} in warning zone but recovery working (peak ${max_loss:.2f}, limit ${max_loss_limit:.2f})'
                }
            elif recovery_active and not is_improving:
                # Recovery active but NOT helping (loss still increasing)
                return {
                    'status': 'warning_recovery_failing',
                    'action': 'close_stack',
                    'current_loss': current_loss,
                    'max_loss': max_loss,
                    'limit': max_loss_limit,
                    'message': f'Stack loss ${current_loss:.2f} - recovery active but failing (peak ${max_loss:.2f}, limit ${max_loss_limit:.2f})',
                    'reason': 'recovery_ineffective'
                }
            else:
                # In warning zone, no recovery - monitor closely
                return {
                    'status': 'warning_no_recovery',
                    'action': 'monitor',
                    'current_loss': current_loss,
                    'limit': max_loss_limit,
                    'message': f'Stack loss ${current_loss:.2f} in warning zone (limit ${max_loss_limit:.2f})',
                    'reason': 'approaching_limit'
                }

        else:
            # CRITICAL: Exceeded 3x stake limit
            return {
                'status': 'critical',
                'action': 'close_stack',
                'current_loss': current_loss,
                'limit': max_loss_limit,
                'message': f'Stack loss ${current_loss:.2f} exceeded 3x stake limit ${max_loss_limit:.2f}',
                'reason': '3x_stake_exceeded'
            }

    def reset_stack(self, ticket: int):
        """Reset tracking for a stack (after close)"""
        self.stack_max_drawdown.pop(ticket, None)
        self.stack_recovery_active.pop(ticket, None)
        self.stack_last_check.pop(ticket, None)
        self.stack_initial_volume.pop(ticket, None)
        self.stack_max_loss_limit.pop(ticket, None)

    def get_stack_health(self, ticket: int) -> Dict:
        """Get health metrics for a stack"""
        return {
            'max_drawdown': self.stack_max_drawdown.get(ticket, 0.0),
            'recovery_active': self.stack_recovery_active.get(ticket, False),
            'last_check': self.stack_last_check.get(ticket),
        }

    def get_all_stats(self) -> Dict:
        """Get statistics across all tracked stacks"""
        if not self.stack_max_drawdown:
            return {
                'total_stacks': 0,
                'avg_max_loss': 0.0,
                'worst_loss': 0.0,
                'stacks_with_recovery': 0,
            }

        return {
            'total_stacks': len(self.stack_max_drawdown),
            'avg_max_loss': sum(self.stack_max_drawdown.values()) / len(self.stack_max_drawdown),
            'worst_loss': max(self.stack_max_drawdown.values()),
            'stacks_with_recovery': sum(1 for active in self.stack_recovery_active.values() if active),
        }
