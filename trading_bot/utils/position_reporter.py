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
            recovery_status: Recovery status from RecoveryManager (from tracked_positions)
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

        # Use tracked position's open_time (set by bot) instead of MT5 time to avoid timezone issues
        entry_time = recovery_status.get('open_time', datetime.now())

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

        # Recovery info - recovery_status is the actual tracked position data
        grid_levels = len(recovery_status.get('grid_levels', []))
        hedge_count = len(recovery_status.get('hedge_tickets', []))
        dca_levels = len(recovery_status.get('dca_levels', []))

        # Time remaining
        time_remaining = max_hold_hours * 3600 - age.total_seconds()
        time_remaining_str = self._format_seconds(time_remaining) if time_remaining > 0 else "EXPIRED"

        if concise:
            # Concise format (3-5 lines)
            summary = f"\n[{ticket}] {symbol} {pos_type}"
            summary += f"\n   {entry_price:.5f} -> {current_price:.5f} | "
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

            # Status indicator
            if profit_percent >= 90:
                status = "[CLOSE SOON]"
            elif profit >= 0:
                status = "[PROFIT]"
            else:
                status = f"[UNDERWATER {abs(pips):.1f} pips]"

            summary += f"\n   {' | '.join(exit_parts)} | {status}"

        else:
            # Detailed format (10+ lines)
            summary = f"\n{'='*80}"
            summary += f"\n[Position {ticket}] {symbol}"
            summary += f"\n{'='*80}"
            summary += f"\n  Direction: {pos_type}"
            summary += f"\n  Entry: {entry_price:.5f} @ {entry_time.strftime('%Y-%m-%d %H:%M:%S')}"
            summary += f"\n  Current: {current_price:.5f}"
            summary += f"\n  P&L: ${profit:+.2f} ({pips:+.1f} pips)"
            summary += f"\n  Age: {age_str}"
            summary += f"\n"
            summary += f"\n  Recovery Status:"
            summary += f"\n  |- Grid: {grid_levels}/4 levels"
            summary += f"\n  |- Hedge: {hedge_count}/1"
            summary += f"\n  \- DCA: {dca_levels}/8 levels"
            summary += f"\n"
            summary += f"\n  Exit Conditions:"
            summary += f"\n  |- Profit Target: ${profit_target:.2f} ({profit_percent:.0f}% there)"
            summary += f"\n  \- Time Limit: {time_remaining_str} remaining"

            if profit_percent >= 90:
                summary += f"\n"
                summary += f"\n  ACTION: Close soon - near profit target!"
            elif profit >= 0:
                summary += f"\n"
                summary += f"\n  ACTION: HOLD - Position profitable"
            else:
                summary += f"\n"
                summary += f"\n  ACTION: HOLD - Managing drawdown with recovery"

        return summary

    def detect_orphaned_positions(
        self,
        mt5_positions: List[Dict],
        recovery_manager
    ) -> Dict:
        """
        Detect orphaned positions and recovery trades

        Returns dict with:
            - orphaned_parent: Positions in MT5 but not tracked by recovery manager
            - orphaned_recovery: Recovery trades with no parent position
            - managed: Positions properly tracked
        """
        tracked_tickets = set(recovery_manager.tracked_positions.keys())
        mt5_tickets = {p['ticket'] for p in mt5_positions}

        # Get all recovery trade tickets from tracked positions
        recovery_tickets = set()
        parent_map = {}  # Maps recovery ticket to parent ticket

        for ticket, pos_data in recovery_manager.tracked_positions.items():
            # Grid tickets
            for grid in pos_data.get('grid_levels', []):
                if 'ticket' in grid and grid['ticket']:
                    recovery_tickets.add(grid['ticket'])
                    parent_map[grid['ticket']] = ticket

            # Hedge tickets
            for hedge in pos_data.get('hedge_tickets', []):
                if 'ticket' in hedge and hedge['ticket']:
                    recovery_tickets.add(hedge['ticket'])
                    parent_map[hedge['ticket']] = ticket

            # DCA tickets
            for dca in pos_data.get('dca_levels', []):
                if 'ticket' in dca and dca['ticket']:
                    recovery_tickets.add(dca['ticket'])
                    parent_map[dca['ticket']] = ticket

        # Orphaned parent positions: In MT5 but not tracked
        # Exclude recovery trades from orphan check
        orphaned_parent = []
        for pos in mt5_positions:
            ticket = pos['ticket']
            if ticket not in tracked_tickets and ticket not in recovery_tickets:
                orphaned_parent.append(pos)

        # Orphaned recovery trades: Parent position closed but recovery trade still open
        orphaned_recovery = []
        for pos in mt5_positions:
            ticket = pos['ticket']
            if ticket in recovery_tickets:
                parent_ticket = parent_map.get(ticket)
                # Check if parent is still open in MT5
                if parent_ticket not in mt5_tickets:
                    orphaned_recovery.append({
                        'position': pos,
                        'parent_ticket': parent_ticket,
                        'recovery_type': self._get_recovery_type(ticket, parent_ticket, recovery_manager)
                    })

        # Properly managed positions
        managed = [pos for pos in mt5_positions if pos['ticket'] in tracked_tickets]

        return {
            'orphaned_parent': orphaned_parent,
            'orphaned_recovery': orphaned_recovery,
            'managed': managed,
            'parent_map': parent_map
        }

    def _get_recovery_type(self, ticket: int, parent_ticket: int, recovery_manager) -> str:
        """Determine if recovery trade is Grid, Hedge, or DCA"""
        if parent_ticket not in recovery_manager.tracked_positions:
            return "Unknown"

        pos_data = recovery_manager.tracked_positions[parent_ticket]

        for grid in pos_data.get('grid_levels', []):
            if grid.get('ticket') == ticket:
                return "Grid"

        for hedge in pos_data.get('hedge_tickets', []):
            if hedge.get('ticket') == ticket:
                return "Hedge"

        for dca in pos_data.get('dca_levels', []):
            if dca.get('ticket') == ticket:
                return "DCA"

        return "Unknown"

    def generate_management_tree(
        self,
        parent_position: Dict,
        recovery_manager,
        all_mt5_positions: List[Dict]
    ) -> str:
        """
        Generate visual tree showing parent position and all recovery trades

        Example output:
        📊 #5963831212 (EURUSD SELL) - PARENT
        ├─ 🔹 Grid L1: #5963831300 (0.03 lots @ 1.17396)
        ├─ 🔹 Grid L2: #5963831401 (0.03 lots @ 1.17476)
        └─ 🛡️  Hedge: #5963831502 (0.15 lots @ 1.17396)
        """
        ticket = parent_position['ticket']
        # Get actual tracked position data (not summary)
        tracked_pos = recovery_manager.tracked_positions.get(ticket)

        if not tracked_pos:
            return f"[{ticket}] - NOT MANAGED [WARNING]"

        tree = f"[{ticket}] {parent_position['symbol']} {parent_position['type'].upper()} - PARENT"

        # Create MT5 position lookup
        mt5_lookup = {p['ticket']: p for p in all_mt5_positions}

        # Grid levels
        grid_levels = tracked_pos.get('grid_levels', [])
        hedge_tickets = tracked_pos.get('hedge_tickets', [])
        dca_levels = tracked_pos.get('dca_levels', [])

        for i, grid in enumerate(grid_levels):
            grid_ticket = grid.get('ticket')
            is_last_grid = (i == len(grid_levels) - 1) and not hedge_tickets and not dca_levels
            prefix = "\-" if is_last_grid else "|-"

            if grid_ticket and grid_ticket in mt5_lookup:
                mt5_pos = mt5_lookup[grid_ticket]
                status = "[OPEN]"
                price = mt5_pos['price_current']
            else:
                status = "[CLOSED]"
                price = grid.get('price', 0)

            tree += f"\n{prefix} Grid L{i+1}: #{grid_ticket} ({grid['volume']:.2f} lots @ {price:.5f}) {status}"

        # Hedge trades
        for i, hedge in enumerate(hedge_tickets):
            hedge_ticket = hedge.get('ticket')
            is_last_hedge = (i == len(hedge_tickets) - 1) and not dca_levels
            prefix = "\-" if is_last_hedge else "|-"

            if hedge_ticket and hedge_ticket in mt5_lookup:
                mt5_pos = mt5_lookup[hedge_ticket]
                status = "[OPEN]"
                volume = mt5_pos.get('volume', hedge.get('volume', 0))
                price = mt5_pos['price_current']
            else:
                status = "[CLOSED]"
                volume = hedge.get('volume', 0)
                price = hedge.get('price', 0)

            tree += f"\n{prefix} Hedge: #{hedge_ticket} ({volume:.2f} lots @ {price:.5f}) {status}"

        # DCA levels
        for i, dca in enumerate(dca_levels):
            dca_ticket = dca.get('ticket')
            is_last = (i == len(dca_levels) - 1)
            prefix = "\-" if is_last else "|-"

            if dca_ticket and dca_ticket in mt5_lookup:
                mt5_pos = mt5_lookup[dca_ticket]
                status = "[OPEN]"
                volume = mt5_pos.get('volume', dca.get('volume', 0))
                price = mt5_pos['price_current']
            else:
                status = "[CLOSED]"
                volume = dca.get('volume', 0)
                price = dca.get('price', 0)

            tree += f"\n{prefix} DCA L{i+1}: #{dca_ticket} ({volume:.2f} lots @ {price:.5f}) {status}"

        return tree

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

        Now includes:
        - Orphan detection
        - Management tree showing parent-child relationships
        - Clear warnings for unmanaged positions

        Returns:
            Formatted status report string
        """
        if not positions:
            return "\n[STATUS REPORT] No open positions"

        # Detect orphaned positions
        orphan_analysis = self.detect_orphaned_positions(positions, recovery_manager)

        report = "\n" + "="*80
        report += f"\n[POSITION STATUS REPORT] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        report += "\n" + "="*80

        # Overall stats
        total_pnl = sum(p.get('profit', 0) for p in positions)
        managed_count = len(orphan_analysis['managed'])
        orphan_parent_count = len(orphan_analysis['orphaned_parent'])
        orphan_recovery_count = len(orphan_analysis['orphaned_recovery'])

        report += f"\n[SUMMARY] {len(positions)} total position(s) | Total P&L: ${total_pnl:+.2f}"
        report += f"\n   Managed: {managed_count} | Orphaned Parents: {orphan_parent_count} | Orphaned Recovery: {orphan_recovery_count}"

        # Managed positions with recovery details
        if orphan_analysis['managed']:
            report += "\n\n" + "-"*80
            report += "\n[MANAGED POSITIONS]"
            report += "\n" + "-"*80

            for position in orphan_analysis['managed']:
                ticket = position['ticket']
                # Get actual tracked position data (not summary)
                tracked_pos = recovery_manager.tracked_positions.get(ticket)

                if tracked_pos:
                    # Standard position summary (pass tracked position data directly)
                    summary = self.generate_position_summary(
                        position=position,
                        recovery_status=tracked_pos,  # Pass full tracked data, not summary
                        account_balance=account_info.get('balance', 10000),
                        profit_target_percent=profit_target_percent,
                        max_hold_hours=max_hold_hours,
                        concise=concise
                    )
                    report += summary

        # Orphaned parent positions (WARNING!)
        if orphan_analysis['orphaned_parent']:
            report += "\n\n" + "-"*80
            report += "\n[WARNING] ORPHANED PARENT POSITIONS - NOT MANAGED BY BOT!"
            report += "\n" + "-"*80
            report += "\n[!] These positions are open but not tracked by recovery system"
            report += "\n[!] No Grid/Hedge/DCA protection will be applied"

            for pos in orphan_analysis['orphaned_parent']:
                report += f"\n\n[{pos['ticket']}] {pos['symbol']} {pos['type'].upper()}"
                report += f"\n   Entry: {pos['price_open']:.5f} | Current: {pos['price_current']:.5f}"
                report += f"\n   P&L: ${pos.get('profit', 0):+.2f}"
                report += f"\n   [STATUS] ORPHANED - Add to tracking or close manually!"

        # Orphaned recovery trades (CRITICAL WARNING!)
        if orphan_analysis['orphaned_recovery']:
            report += "\n\n" + "-"*80
            report += "\n[CRITICAL] ORPHANED RECOVERY TRADES - PARENT POSITION CLOSED!"
            report += "\n" + "-"*80
            report += "\n[!] These recovery trades are still open but their parent position is closed"
            report += "\n[!] They should be manually reviewed and closed"

            for orphan in orphan_analysis['orphaned_recovery']:
                pos = orphan['position']
                parent = orphan['parent_ticket']
                rec_type = orphan['recovery_type']

                report += f"\n\n[{rec_type}] Trade #{pos['ticket']} (Parent was #{parent})"
                report += f"\n   Symbol: {pos['symbol']} {pos['type'].upper()}"
                report += f"\n   Entry: {pos['price_open']:.5f} | Current: {pos['price_current']:.5f}"
                report += f"\n   P&L: ${pos.get('profit', 0):+.2f}"
                report += f"\n   [ACTION] Manual review required - close or re-parent!"

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
                f"[ALERT] APPROACHING TARGET - Position #{position['ticket']} "
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
                f"[GRID L{level}] ADDED - Position #{ticket}\n"
                f"   Price: {price:.5f} | Volume: {volume:.2f} lots\n"
                f"   Reason: Price moved {details.get('pips', 0):.1f} pips against position"
            )

        elif action_type == 'hedge':
            volume = details.get('volume', 0)
            trigger_pips = details.get('trigger_pips', 0)
            return (
                f"[HEDGE] ACTIVATED - Position #{ticket}\n"
                f"   Volume: {volume:.2f} lots ({details.get('ratio', 0):.1f}x)\n"
                f"   Triggered at: {trigger_pips:.1f} pips underwater"
            )

        elif action_type == 'dca':
            level = details.get('level', '?')
            price = details.get('price', 0)
            volume = details.get('volume', 0)
            return (
                f"[DCA L{level}] ADDED - Position #{ticket}\n"
                f"   Price: {price:.5f} | Volume: {volume:.2f} lots\n"
                f"   Total exposure: {details.get('total_volume', 0):.2f} lots"
            )

        return f"[RECOVERY] {action_type}"

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
        result = "[WIN]" if profit > 0 else "[LOSS]"
        pips = abs(exit_price - entry_price) * 10000

        message = f"\n{result} POSITION CLOSED - #{ticket}"
        message += f"\n   Entry: {entry_price:.5f} -> Exit: {exit_price:.5f}"
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
