"""
Position Status Reporter
Provides human-readable status updates for open positions
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta


class PositionStatusReporter:
    """Generate human-readable status reports for positions"""

    def __init__(self):
        """Initialize reporter"""
        self.last_report_time = None

    def should_report(self, interval_minutes: int) -> bool:
        """Check if it's time for a status report"""
        if self.last_report_time is None:
            return True

        elapsed = (datetime.now() - self.last_report_time).total_seconds() / 60
        return elapsed >= interval_minutes

    def generate_position_summary(
        self,
        position: Dict,
        recovery_status: Dict,
        account_balance: float,
        profit_target_percent: float,
        max_hold_hours: int,
        concise: bool = True
    ) -> str:
        """
        Generate human-readable summary for a single position

        Args:
            position: Position dict from MT5
            recovery_status: Recovery status from RecoveryManager
            account_balance: Account balance for profit calculation
            profit_target_percent: Profit target percentage
            max_hold_hours: Maximum hold time in hours
            concise: If True, use 3-5 lines; if False, use detailed format

        Returns:
            Formatted string summary
        """
        ticket = position['ticket']
        symbol = position['symbol']
        pos_type = position['type'].upper()
        entry_price = position['price_open']
        current_price = position['price_current']
        profit = position.get('profit', 0)
        entry_time = position.get('time', datetime.now())

        # Calculate age
        if isinstance(entry_time, datetime):
            age = datetime.now() - entry_time
            age_str = self._format_timedelta(age)
        else:
            age_str = "Unknown"

        # Calculate pips
        pips = abs(current_price - entry_price) * 10000
        if pos_type == 'SELL':
            pips *= 1 if current_price < entry_price else -1
        else:
            pips *= 1 if current_price > entry_price else -1

        # Calculate profit target
        profit_target = account_balance * (profit_target_percent / 100)
        profit_percent = (profit / profit_target * 100) if profit_target > 0 else 0

        # Recovery info
        grid_levels = len(recovery_status.get('grid_levels', []))
        hedge_count = len(recovery_status.get('hedge_tickets', []))
        dca_levels = len(recovery_status.get('dca_levels', []))

        # Time remaining
        time_remaining = max_hold_hours * 3600 - age.total_seconds()
        time_remaining_str = self._format_seconds(time_remaining) if time_remaining > 0 else "EXPIRED"

        if concise:
            # Concise format (3-5 lines)
            summary = f"\n📊 #{ticket} ({symbol} {pos_type})"
            summary += f"\n   {entry_price:.5f} → {current_price:.5f} | "
            summary += f"${profit:+.2f} ({pips:+.1f} pips) | Age: {age_str}"

            # Recovery status (one line)
            recovery_parts = []
            if grid_levels > 0:
                recovery_parts.append(f"Grid:{grid_levels}")
            if hedge_count > 0:
                recovery_parts.append(f"Hedge:{hedge_count}")
            if dca_levels > 0:
                recovery_parts.append(f"DCA:{dca_levels}")

            if recovery_parts:
                summary += f"\n   Recovery: {' | '.join(recovery_parts)}"

            # Exit status (one line)
            exit_parts = []
            if profit_target > 0:
                exit_parts.append(f"Target:{profit_percent:.0f}% (${profit:.2f}/${profit_target:.2f})")
            exit_parts.append(f"Time:{time_remaining_str}")

            summary += f"\n   {' | '.join(exit_parts)}"

            # Action
            if profit_percent >= 90:
                summary += f" | ⚠️  CLOSE SOON"
            elif profit >= 0:
                summary += f" | ✅ HOLD"
            else:
                summary += f" | 📉 Underwater"

        else:
            # Detailed format (10+ lines)
            summary = f"\n{'='*80}"
            summary += f"\n📊 Position #{ticket} ({symbol})"
            summary += f"\n{'='*80}"
            summary += f"\n  Direction: {pos_type}"
            summary += f"\n  Entry: {entry_price:.5f} @ {entry_time.strftime('%Y-%m-%d %H:%M:%S')}"
            summary += f"\n  Current: {current_price:.5f}"
            summary += f"\n  P&L: ${profit:+.2f} ({pips:+.1f} pips)"
            summary += f"\n  Age: {age_str}"
            summary += f"\n"
            summary += f"\n  Recovery Status:"
            summary += f"\n  ├─ Grid: {grid_levels}/4 levels"
            summary += f"\n  ├─ Hedge: {hedge_count}/1"
            summary += f"\n  └─ DCA: {dca_levels}/8 levels"
            summary += f"\n"
            summary += f"\n  Exit Conditions:"
            summary += f"\n  ├─ Profit Target: ${profit_target:.2f} ({profit_percent:.0f}% there)"
            summary += f"\n  └─ Time Limit: {time_remaining_str} remaining"

            if profit_percent >= 90:
                summary += f"\n"
                summary += f"\n  ⚠️  ACTION: Close soon - near profit target!"
            elif profit >= 0:
                summary += f"\n"
                summary += f"\n  ✅ ACTION: HOLD - Position profitable"
            else:
                summary += f"\n"
                summary += f"\n  📉 ACTION: HOLD - Managing drawdown with recovery"

        return summary

    def generate_status_report(
        self,
        positions: List[Dict],
        recovery_manager,
        account_info: Dict,
        profit_target_percent: float,
        max_hold_hours: int,
        concise: bool = True
    ) -> str:
        """
        Generate complete status report for all positions

        Returns:
            Formatted status report string
        """
        if not positions:
            return "\n📊 STATUS REPORT: No open positions"

        report = "\n" + "="*80
        report += f"\n📊 POSITION STATUS REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        report += "\n" + "="*80

        # Overall stats
        total_pnl = sum(p.get('profit', 0) for p in positions)
        report += f"\n📈 {len(positions)} position(s) | Total P&L: ${total_pnl:+.2f}"

        # Individual positions
        for position in positions:
            ticket = position['ticket']
            recovery_status = recovery_manager.get_position_status(ticket)

            if recovery_status:
                summary = self.generate_position_summary(
                    position=position,
                    recovery_status=recovery_status,
                    account_balance=account_info.get('balance', 10000),
                    profit_target_percent=profit_target_percent,
                    max_hold_hours=max_hold_hours,
                    concise=concise
                )
                report += summary

        report += "\n" + "="*80

        # Update last report time
        self.last_report_time = datetime.now()

        return report

    def check_exit_proximity(
        self,
        position: Dict,
        account_balance: float,
        profit_target_percent: float,
        proximity_threshold: float = 90.0
    ) -> Optional[str]:
        """
        Check if position is close to exit target

        Returns:
            Alert message if close to target, None otherwise
        """
        profit = position.get('profit', 0)
        profit_target = account_balance * (profit_target_percent / 100)

        if profit_target <= 0:
            return None

        profit_percent = (profit / profit_target) * 100

        if profit_percent >= proximity_threshold:
            return (
                f"⚠️  APPROACHING TARGET - Position #{position['ticket']} "
                f"at {profit_percent:.0f}% of profit target "
                f"(${profit:.2f}/${profit_target:.2f})"
            )

        return None

    def format_recovery_action(
        self,
        action_type: str,
        ticket: int,
        details: Dict
    ) -> str:
        """
        Format recovery action message

        Args:
            action_type: 'grid', 'hedge', or 'dca'
            ticket: Original position ticket
            details: Action details dict

        Returns:
            Formatted message
        """
        if action_type == 'grid':
            level = details.get('level', '?')
            price = details.get('price', 0)
            volume = details.get('volume', 0)
            return (
                f"🔹 GRID L{level} ADDED - Position #{ticket}\n"
                f"   Price: {price:.5f} | Volume: {volume:.2f} lots\n"
                f"   Reason: Price moved {details.get('pips', 0):.1f} pips against position"
            )

        elif action_type == 'hedge':
            volume = details.get('volume', 0)
            trigger_pips = details.get('trigger_pips', 0)
            return (
                f"🛡️  HEDGE ACTIVATED - Position #{ticket}\n"
                f"   Volume: {volume:.2f} lots ({details.get('ratio', 0):.1f}x)\n"
                f"   Triggered at: {trigger_pips:.1f} pips underwater"
            )

        elif action_type == 'dca':
            level = details.get('level', '?')
            price = details.get('price', 0)
            volume = details.get('volume', 0)
            return (
                f"💰 DCA L{level} ADDED - Position #{ticket}\n"
                f"   Price: {price:.5f} | Volume: {volume:.2f} lots\n"
                f"   Total exposure: {details.get('total_volume', 0):.2f} lots"
            )

        return f"Recovery action: {action_type}"

    def format_position_close(
        self,
        ticket: int,
        entry_price: float,
        exit_price: float,
        profit: float,
        hold_time: timedelta,
        close_reason: str,
        recovery_used: Dict
    ) -> str:
        """
        Format position close message

        Returns:
            Formatted close message
        """
        direction = "🟢" if profit > 0 else "🔴"
        pips = abs(exit_price - entry_price) * 10000

        message = f"\n{direction} POSITION CLOSED - #{ticket}"
        message += f"\n   Entry: {entry_price:.5f} → Exit: {exit_price:.5f}"
        message += f"\n   P&L: ${profit:+.2f} ({pips:.1f} pips) | Held: {self._format_timedelta(hold_time)}"
        message += f"\n   Reason: {close_reason}"

        # Recovery contribution
        if recovery_used:
            grid_levels = len(recovery_used.get('grid_levels', []))
            hedge_count = len(recovery_used.get('hedge_tickets', []))
            dca_levels = len(recovery_used.get('dca_levels', []))

            if grid_levels > 0 or hedge_count > 0 or dca_levels > 0:
                message += f"\n   Recovery: Grid×{grid_levels} Hedge×{hedge_count} DCA×{dca_levels}"

        return message

    @staticmethod
    def _format_timedelta(td: timedelta) -> str:
        """Format timedelta as human-readable string"""
        total_seconds = int(td.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes}m"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"
        else:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            return f"{days}d {hours}h"

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        """Format seconds as human-readable string"""
        return PositionStatusReporter._format_timedelta(timedelta(seconds=seconds))
