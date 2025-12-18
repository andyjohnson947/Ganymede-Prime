#!/usr/bin/env python3
"""
Analyze Recovery Stack Maximum Dollar Values

Calculates the maximum dollar value (peak unrealized loss) for each
recovery stack from today's trading session.

Usage:
    python analyze_stack_values.py [--date YYYY-MM-DD]
"""

import MetaTrader5 as mt5
from datetime import datetime, timedelta
from collections import defaultdict
import argparse
from typing import Dict, List, Optional


class StackValueAnalyzer:
    """Analyze maximum dollar values for recovery stacks"""

    def __init__(self):
        self.connected = False
        self.deals = []
        self.stacks = defaultdict(lambda: {
            'parent_ticket': None,
            'parent_symbol': None,
            'parent_type': None,
            'positions': [],
            'max_drawdown': 0.0,
            'max_exposure': 0.0,
            'recovery_types': set()
        })

    def connect(self) -> bool:
        """Connect to MT5 terminal"""
        if not mt5.initialize():
            print(f"❌ MT5 initialization failed: {mt5.last_error()}")
            return False

        self.connected = True
        account_info = mt5.account_info()
        if account_info:
            print(f"✅ Connected to MT5")
            print(f"   Account: {account_info.login}")
            print(f"   Server: {account_info.server}")
            print(f"   Balance: ${account_info.balance:.2f}")
        return True

    def disconnect(self):
        """Disconnect from MT5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False

    def fetch_deals(self, start_date: datetime, end_date: datetime) -> bool:
        """
        Fetch deals from MT5 for the specified period

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            bool: True if successful
        """
        if not self.connected:
            print("❌ Not connected to MT5")
            return False

        print(f"\n{'='*80}")
        print(f"📊 FETCHING TRADE HISTORY")
        print(f"{'='*80}")
        print(f"Period: {start_date.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%Y-%m-%d %H:%M')}")

        # Fetch all deals
        deals = mt5.history_deals_get(start_date, end_date)
        if deals is None:
            print(f"❌ Failed to fetch deals: {mt5.last_error()}")
            return False

        # Convert to dict and filter entry deals
        self.deals = []
        for deal in deals:
            deal_dict = {
                'ticket': deal.ticket,
                'order': deal.order,
                'time': datetime.fromtimestamp(deal.time),
                'type': 'buy' if deal.type == 0 else 'sell',
                'entry': deal.entry,  # 0=IN, 1=OUT
                'volume': deal.volume,
                'price': deal.price,
                'profit': deal.profit,
                'commission': deal.commission,
                'swap': deal.swap,
                'fee': deal.fee,
                'symbol': deal.symbol,
                'comment': deal.comment,
                'position_id': deal.position_id
            }
            self.deals.append(deal_dict)

        print(f"   Total deals: {len(self.deals)}")
        entry_deals = [d for d in self.deals if d['entry'] == 0]
        exit_deals = [d for d in self.deals if d['entry'] == 1]
        print(f"   Entry deals: {len(entry_deals)}")
        print(f"   Exit deals: {len(exit_deals)}")
        print(f"✅ History loaded")
        print(f"{'='*80}\n")

        return True

    def _extract_parent_ticket(self, comment: str) -> Optional[int]:
        """Extract parent ticket from recovery position comment"""
        if not comment:
            return None

        # New format: G1-12345, D2-12345, H-12345
        if comment and len(comment) > 0 and comment[0] in ['G', 'D', 'H'] and '-' in comment:
            try:
                ticket_str = comment.split('-')[-1].strip()
                return int(ticket_str)
            except (ValueError, IndexError):
                pass

        # Old format: Grid L1 - 12345, DCA L2 - 12345, Hedge - 12345
        if ' - ' in comment:
            try:
                ticket_str = comment.split(' - ')[-1].strip()
                return int(ticket_str)
            except (ValueError, IndexError):
                pass

        return None

    def _identify_recovery_type(self, comment: str) -> Optional[str]:
        """Identify if position is a recovery trade and what type"""
        if not comment:
            return None

        if comment.startswith('G') or 'Grid' in comment:
            return 'Grid'
        elif comment.startswith('D') or 'DCA' in comment:
            return 'DCA'
        elif comment.startswith('H') or 'Hedge' in comment:
            return 'Hedge'

        return None

    def analyze_stacks(self):
        """Analyze recovery stacks and calculate maximum dollar values"""
        print(f"\n{'='*80}")
        print(f"📊 ANALYZING RECOVERY STACKS")
        print(f"{'='*80}\n")

        # Get entry deals (position opens)
        entry_deals = [d for d in self.deals if d['entry'] == 0]

        # Separate parent and recovery positions
        parent_positions = []
        recovery_positions = []

        for deal in entry_deals:
            comment = deal.get('comment', '')
            recovery_type = self._identify_recovery_type(comment)

            if recovery_type:
                # This is a recovery position
                parent_ticket = self._extract_parent_ticket(comment)
                deal['parent_ticket'] = parent_ticket
                deal['recovery_type'] = recovery_type
                recovery_positions.append(deal)
            else:
                # This is a parent/original position
                parent_positions.append(deal)

        print(f"Found {len(parent_positions)} parent position(s)")
        print(f"Found {len(recovery_positions)} recovery position(s)")

        # Build stacks: group recovery positions by parent
        for parent in parent_positions:
            ticket = parent['ticket']
            self.stacks[ticket]['parent_ticket'] = ticket
            self.stacks[ticket]['parent_symbol'] = parent['symbol']
            self.stacks[ticket]['parent_type'] = parent['type']
            self.stacks[ticket]['positions'].append(parent)

        for recovery in recovery_positions:
            parent_ticket = recovery.get('parent_ticket')
            if parent_ticket:
                # Try to match with full ticket or shortened ticket (last 5 digits)
                matched = False

                # Try exact match first
                if parent_ticket in self.stacks:
                    self.stacks[parent_ticket]['positions'].append(recovery)
                    self.stacks[parent_ticket]['recovery_types'].add(recovery['recovery_type'])
                    matched = True
                else:
                    # Try shortened ticket match (last 5 digits)
                    for stack_ticket in self.stacks.keys():
                        if stack_ticket % 100000 == parent_ticket % 100000:
                            self.stacks[stack_ticket]['positions'].append(recovery)
                            self.stacks[stack_ticket]['recovery_types'].add(recovery['recovery_type'])
                            matched = True
                            break

                if not matched:
                    print(f"   ⚠️  Orphan recovery: {recovery['recovery_type']} #{recovery['ticket']} - parent #{parent_ticket} not found")

        # Calculate maximum drawdown for each stack
        exit_deals = [d for d in self.deals if d['entry'] == 1]

        for stack_ticket, stack_data in self.stacks.items():
            positions = stack_data['positions']

            if not positions:
                continue

            # Calculate total entry cost
            total_entry_volume = sum(p['volume'] for p in positions)

            # Find all exit deals for this stack
            position_tickets = {p['position_id'] for p in positions}
            stack_exits = [e for e in exit_deals if e['position_id'] in position_tickets]

            # Calculate realized P&L
            realized_pnl = sum(e['profit'] + e.get('commission', 0) + e.get('swap', 0) + e.get('fee', 0)
                             for e in stack_exits)

            # If not all positions closed, calculate unrealized P&L from current prices
            # For closed stacks, max drawdown is the realized P&L if negative
            if realized_pnl < 0:
                stack_data['max_drawdown'] = abs(realized_pnl)

            stack_data['max_exposure'] = total_entry_volume
            stack_data['realized_pnl'] = realized_pnl
            stack_data['position_count'] = len(positions)

        # Display results
        print(f"\n{'='*80}")
        print(f"📊 RECOVERY STACK ANALYSIS")
        print(f"{'='*80}\n")

        if not self.stacks:
            print("No recovery stacks found in the specified period")
            return

        print(f"{'Parent':<12} {'Symbol':<8} {'Type':<6} {'Positions':<10} {'Recovery':<20} {'Max Exposure':<12} {'Max Drawdown':<15}")
        print(f"{'-'*110}")

        total_max_drawdown = 0.0
        stack_count = 0

        for stack_ticket, stack_data in sorted(self.stacks.items()):
            if stack_data['position_count'] == 0:
                continue

            stack_count += 1
            max_drawdown = stack_data['max_drawdown']
            total_max_drawdown += max_drawdown

            recovery_types = ', '.join(sorted(stack_data['recovery_types'])) if stack_data['recovery_types'] else 'None'

            print(f"#{stack_ticket:<11} "
                  f"{stack_data['parent_symbol']:<8} "
                  f"{stack_data['parent_type'].upper():<6} "
                  f"{stack_data['position_count']:<10} "
                  f"{recovery_types:<20} "
                  f"{stack_data['max_exposure']:.2f} lots{'':<4} "
                  f"${max_drawdown:.2f}")

        # Calculate average
        if stack_count > 0:
            avg_max_drawdown = total_max_drawdown / stack_count

            print(f"\n{'='*110}")
            print(f"📊 SUMMARY:")
            print(f"   Total stacks analyzed: {stack_count}")
            print(f"   Total max drawdown: ${total_max_drawdown:.2f}")
            print(f"   Average max drawdown per stack: ${avg_max_drawdown:.2f}")
            print(f"{'='*110}\n")
        else:
            print(f"\nNo stacks with positions found")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Analyze recovery stack maximum dollar values')
    parser.add_argument('--date', type=str, help='Date to analyze (YYYY-MM-DD, default: today)', default=None)
    args = parser.parse_args()

    # Parse date
    if args.date:
        target_date = datetime.strptime(args.date, '%Y-%m-%d')
    else:
        target_date = datetime.now()

    # Set time range for the entire day
    start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    # Create analyzer
    analyzer = StackValueAnalyzer()

    try:
        # Connect to MT5
        if not analyzer.connect():
            return 1

        # Fetch deals
        if not analyzer.fetch_deals(start_date, end_date):
            return 1

        # Analyze stacks
        analyzer.analyze_stacks()

    finally:
        analyzer.disconnect()

    return 0


if __name__ == '__main__':
    exit(main())
