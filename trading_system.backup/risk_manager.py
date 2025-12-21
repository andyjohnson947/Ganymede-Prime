"""
Risk Management System
Circuit breakers and risk controls
"""

import trading_config as config
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from position_managers import Position


class RiskManager:
    """Manages risk controls and circuit breakers"""

    def __init__(self, initial_balance: float):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.peak_balance = initial_balance
        self.daily_profit = 0.0
        self.consecutive_losses = 0
        self.trading_enabled = True
        self.circuit_breaker_triggered = False
        self.daily_reset_time = None

    def update_balance(self, balance: float):
        """Update current balance and peak"""
        self.current_balance = balance
        if balance > self.peak_balance:
            self.peak_balance = balance

    def calculate_drawdown_pct(self) -> float:
        """Calculate current drawdown percentage"""
        if self.peak_balance == 0:
            return 0.0

        drawdown = (self.peak_balance - self.current_balance) / self.peak_balance * 100
        return drawdown

    def calculate_daily_profit_pct(self) -> float:
        """Calculate today's profit percentage"""
        if self.initial_balance == 0:
            return 0.0

        return (self.daily_profit / self.initial_balance) * 100

    def check_max_drawdown(self) -> bool:
        """
        Check if max drawdown limit exceeded

        Returns:
            True if safe to trade, False if circuit breaker triggered
        """
        drawdown_pct = self.calculate_drawdown_pct()

        if drawdown_pct >= config.MAX_DRAWDOWN_PCT:
            self.circuit_breaker_triggered = True
            self.trading_enabled = False
            return False

        return True

    def check_daily_loss_limit(self) -> bool:
        """
        Check if daily loss limit exceeded

        Returns:
            True if safe to trade, False if limit hit
        """
        daily_loss_pct = abs(self.calculate_daily_profit_pct())

        if self.daily_profit < 0 and daily_loss_pct >= config.MAX_DAILY_LOSS_PCT:
            return False

        return True

    def record_trade_result(self, profit: float):
        """Record trade result and update consecutive losses"""
        self.daily_profit += profit

        if profit < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

    def check_consecutive_losses(self) -> bool:
        """
        Check if consecutive loss limit exceeded

        Returns:
            True if safe to trade, False if too many losses
        """
        if self.consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
            return False

        return True

    def check_position_limits(self, current_positions: List[Position],
                             symbol: str) -> bool:
        """
        Check if position limits allow new positions

        Returns:
            True if can open more positions, False if limits reached
        """
        # Check total positions
        open_positions = [p for p in current_positions if p.is_open]

        if len(open_positions) >= config.MAX_TOTAL_POSITIONS:
            return False

        # Check positions per symbol
        symbol_positions = [p for p in open_positions if p.symbol == symbol]

        if len(symbol_positions) >= config.MAX_POSITIONS_PER_SYMBOL:
            return False

        # Check total exposure
        total_lots = sum(p.lot_size for p in open_positions)

        if total_lots >= config.MAX_EXPOSURE_LOTS:
            return False

        return True

    def check_time_filter(self, current_time: datetime) -> bool:
        """
        Check if current time is within trading hours

        Returns:
            True if safe to trade, False if outside hours
        """
        hour = current_time.hour

        # Check avoid hours
        if hour in config.AVOID_HOURS:
            return False

        # Check trading window
        if hour < config.TRADING_START_HOUR or hour > config.TRADING_END_HOUR:
            return False

        return True

    def reset_daily_stats(self):
        """Reset daily statistics (call at start of new trading day)"""
        self.daily_profit = 0.0
        # Don't reset consecutive losses - they carry over

    def can_trade(self, current_positions: List[Position],
                  symbol: str, current_time: datetime) -> Tuple[bool, str]:
        """
        Master check - can we trade?

        Returns:
            (can_trade, reason_if_not)
        """
        # Check circuit breaker
        if self.circuit_breaker_triggered:
            return False, "Circuit breaker triggered - max drawdown exceeded"

        if not self.trading_enabled:
            return False, "Trading disabled"

        # Check drawdown
        if not self.check_max_drawdown():
            return False, f"Max drawdown ({config.MAX_DRAWDOWN_PCT}%) exceeded"

        # Check daily loss
        if not self.check_daily_loss_limit():
            return False, f"Daily loss limit ({config.MAX_DAILY_LOSS_PCT}%) exceeded"

        # Check consecutive losses
        if not self.check_consecutive_losses():
            return False, f"Too many consecutive losses ({self.consecutive_losses})"

        # Check position limits
        if not self.check_position_limits(current_positions, symbol):
            return False, "Position limits reached"

        # Check time filter
        if not self.check_time_filter(current_time):
            return False, f"Outside trading hours (current hour: {current_time.hour})"

        return True, ""

    def get_risk_status(self) -> Dict:
        """Get current risk status for monitoring"""
        return {
            'trading_enabled': self.trading_enabled,
            'circuit_breaker': self.circuit_breaker_triggered,
            'current_balance': self.current_balance,
            'peak_balance': self.peak_balance,
            'drawdown_pct': self.calculate_drawdown_pct(),
            'daily_profit': self.daily_profit,
            'daily_profit_pct': self.calculate_daily_profit_pct(),
            'consecutive_losses': self.consecutive_losses,
        }
