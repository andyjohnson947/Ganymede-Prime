"""
Stack Drawdown Limiter - Monitors and enforces per-stack loss limits

Key features:
- Fixed $30 USD loss limit per stack (including all recovery trades)
- Tracks recovery effectiveness (is loss decreasing?)
- Auto-closes if stack exceeds $30 loss
- Prevents catastrophic margin exhaustion
"""

from typing import Dict, List, Optional
from datetime import datetime


class StackDrawdownLimiter:
    """Enforces per-stack drawdown limits with recovery-aware logic"""

    def __init__(self, max_loss_usd: float = 30.0):
        """
        Initialize stack limiter

        Args:
            max_loss_usd: Fixed loss limit per stack in USD (default $30)
        """
        self.max_loss_usd = max_loss_usd
        self.warning_threshold = max_loss_usd * 0.80  # 80% of limit = $24

        # Track stack health
        self.stack_max_drawdown = {}  # ticket -> max loss seen
        self.stack_recovery_active = {}  # ticket -> bool (has recovery been triggered?)
        self.stack_last_check = {}  # ticket -> timestamp

    def check_stack_limit(
        self,
        ticket: int,
        current_drawdown: float,
        recovery_active: bool,
        symbol: str,
        initial_volume: float = None
    ) -> Dict:
        """
        Check if stack has exceeded drawdown limit (fixed $30 USD)

        Logic:
        1. Max loss = $30 USD per stack (original + all recovery trades)
        2. Warning zone at $24 (80% of limit)
        3. Auto-close at $30 limit

        Args:
            ticket: Parent position ticket
            current_drawdown: Current stack P&L (negative = loss)
            recovery_active: Whether recovery mechanisms are active
            symbol: Trading symbol
            initial_volume: Not used (kept for compatibility)

        Returns:
            Dict with status and action to take
        """
        # Convert P&L to absolute loss
        current_loss = abs(current_drawdown) if current_drawdown < 0 else 0.0

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
        if current_loss < self.warning_threshold:
            # SAFE: Under $24
            return {
                'status': 'safe',
                'action': 'continue',
                'current_loss': current_loss,
                'limit': self.max_loss_usd,
                'warning_threshold': self.warning_threshold,
                'message': f'Stack loss ${current_loss:.2f} within limit ${self.max_loss_usd:.2f}'
            }

        elif current_loss < self.max_loss_usd:
            # WARNING ZONE: $24-$30
            if recovery_active and is_improving:
                # Recovery is active AND working (loss decreasing)
                return {
                    'status': 'warning_recovery_working',
                    'action': 'monitor',
                    'current_loss': current_loss,
                    'max_loss': max_loss,
                    'limit': self.max_loss_usd,
                    'message': f'Stack loss ${current_loss:.2f} in warning zone but recovery working (peak ${max_loss:.2f}, limit ${self.max_loss_usd:.2f})'
                }
            elif recovery_active and not is_improving:
                # Recovery active but NOT helping (loss still increasing)
                return {
                    'status': 'warning_recovery_failing',
                    'action': 'close_stack',
                    'current_loss': current_loss,
                    'max_loss': max_loss,
                    'limit': self.max_loss_usd,
                    'message': f'Stack loss ${current_loss:.2f} - recovery active but failing (peak ${max_loss:.2f}, limit ${self.max_loss_usd:.2f})',
                    'reason': 'recovery_ineffective'
                }
            else:
                # In warning zone, no recovery - monitor closely
                return {
                    'status': 'warning_no_recovery',
                    'action': 'monitor',
                    'current_loss': current_loss,
                    'limit': self.max_loss_usd,
                    'message': f'Stack loss ${current_loss:.2f} in warning zone (limit ${self.max_loss_usd:.2f})',
                    'reason': 'approaching_limit'
                }

        else:
            # CRITICAL: Exceeded $30 limit
            return {
                'status': 'critical',
                'action': 'close_stack',
                'current_loss': current_loss,
                'limit': self.max_loss_usd,
                'message': f'Stack loss ${current_loss:.2f} exceeded ${self.max_loss_usd:.2f} limit',
                'reason': 'max_loss_exceeded'
            }

    def reset_stack(self, ticket: int):
        """Reset tracking for a stack (after close)"""
        self.stack_max_drawdown.pop(ticket, None)
        self.stack_recovery_active.pop(ticket, None)
        self.stack_last_check.pop(ticket, None)

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
