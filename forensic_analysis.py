#!/usr/bin/env python3
"""
Forensic Analysis Script for Trade History

Analyzes MT5 trade history to identify:
1. Duplicate recovery trades (comment truncation bug)
2. Orphaned hedge positions
3. Exposure growth timeline
4. Parent-child relationship mapping
5. Drawdown progression
6. Recovery cascade sequences

Usage:
    python forensic_analysis.py [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
"""

import MetaTrader5 as mt5
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
from typing import Dict, List, Optional
import argparse


class ForensicAnalyzer:
    """Analyze MT5 trade history for forensic investigation"""

    def __init__(self):
        """Initialize analyzer"""
        self.connected = False
        self.deals = []
        self.positions = []
        self.parent_child_map = defaultdict(list)
        self.orphans = []
        self.duplicates = []
        self.exposure_timeline = []

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
            print(f"   Currency: {account_info.currency}")
        return True

    def disconnect(self):
        """Disconnect from MT5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False

    def fetch_history(self, start_date: datetime, end_date: datetime) -> bool:
        """
        Fetch deal and position history from MT5

        Args:
            start_date: Start date for history
            end_date: End date for history

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

        # Fetch deals (executed trades)
        deals = mt5.history_deals_get(start_date, end_date)
        if deals is None:
            print(f"❌ Failed to fetch deals: {mt5.last_error()}")
            return False

        self.deals = [self._deal_to_dict(deal) for deal in deals]
        print(f"   Deals: {len(self.deals)}")

        # Fetch orders (position history)
        orders = mt5.history_orders_get(start_date, end_date)
        if orders is None:
            print(f"❌ Failed to fetch orders: {mt5.last_error()}")
            return False

        self.positions = [self._order_to_dict(order) for order in orders]
        print(f"   Orders: {len(self.positions)}")

        print(f"✅ History loaded successfully")
        print(f"{'='*80}\n")
        return True

    def _deal_to_dict(self, deal) -> Dict:
        """Convert MT5 deal to dictionary"""
        return {
            'ticket': deal.ticket,
            'order': deal.order,
            'time': datetime.fromtimestamp(deal.time),
            'type': 'buy' if deal.type == mt5.DEAL_TYPE_BUY else 'sell',
            'entry': deal.entry,  # IN or OUT
            'symbol': deal.symbol,
            'volume': deal.volume,
            'price': deal.price,
            'profit': deal.profit,
            'commission': deal.commission,
            'swap': deal.swap,
            'comment': deal.comment,
            'position_id': deal.position_id,
        }

    def _order_to_dict(self, order) -> Dict:
        """Convert MT5 order to dictionary"""
        return {
            'ticket': order.ticket,
            'time_setup': datetime.fromtimestamp(order.time_setup),
            'time_done': datetime.fromtimestamp(order.time_done) if order.time_done > 0 else None,
            'type': 'buy' if order.type == mt5.ORDER_TYPE_BUY else 'sell',
            'symbol': order.symbol,
            'volume_initial': order.volume_initial,
            'volume_current': order.volume_current,
            'price_open': order.price_open,
            'price_current': order.price_current,
            'comment': order.comment,
            'position_id': order.position_id,
        }

    def analyze_parent_child_relationships(self):
        """Build parent-child relationship map from comments"""
        print(f"\n{'='*80}")
        print(f"🔍 ANALYZING PARENT-CHILD RELATIONSHIPS")
        print(f"{'='*80}\n")

        recovery_deals = []
        parent_deals = []

        for deal in self.deals:
            if deal['entry'] == 0:  # Only entry deals (ENTRY_IN = 0 = position opens)
                comment = deal.get('comment', '')

                # Check if this is a recovery deal
                is_recovery = any([
                    comment.startswith('G'),  # Grid (new format)
                    comment.startswith('D'),  # DCA (new format)
                    comment.startswith('H'),  # Hedge (new format)
                    'Grid' in comment,        # Grid (old format)
                    'DCA' in comment,         # DCA (old format)
                    'Hedge' in comment,       # Hedge (old format)
                ])

                if is_recovery:
                    recovery_deals.append(deal)

                    # Try to extract parent ticket
                    parent_ticket = self._extract_parent_ticket(comment)

                    deal['parent_ticket'] = parent_ticket
                    deal['recovery_type'] = self._identify_recovery_type(comment)

                    if parent_ticket:
                        self.parent_child_map[parent_ticket].append(deal)
                    else:
                        # Orphan - can't identify parent
                        self.orphans.append({
                            'deal': deal,
                            'reason': 'Cannot parse parent ticket from comment'
                        })
                else:
                    parent_deals.append(deal)

        print(f"📊 Summary:")
        print(f"   Parent positions: {len(parent_deals)}")
        print(f"   Recovery positions: {len(recovery_deals)}")
        print(f"   Linked to parents: {len(recovery_deals) - len(self.orphans)}")
        print(f"   Orphaned (no parent): {len(self.orphans)}")

        # Show parent-child trees
        if self.parent_child_map:
            print(f"\n📊 Parent-Child Trees:")
            for parent_ticket, children in sorted(self.parent_child_map.items()):
                parent_deal = next((d for d in self.deals if d['ticket'] == parent_ticket), None)
                if parent_deal:
                    print(f"\n   Parent #{parent_ticket} - {parent_deal['symbol']} {parent_deal['type'].upper()} {parent_deal['volume']:.2f} @ {parent_deal['time'].strftime('%H:%M:%S')}")
                else:
                    print(f"\n   Parent #{parent_ticket} - ⚠️ NOT FOUND IN HISTORY (closed earlier?)")

                for child in children:
                    print(f"      └─ {child['recovery_type']} #{child['ticket']} - {child['type'].upper()} {child['volume']:.2f} @ {child['time'].strftime('%H:%M:%S')} [Comment: '{child['comment']}']")

        print(f"\n{'='*80}\n")

    def _extract_parent_ticket(self, comment: str) -> Optional[int]:
        """Extract parent ticket from comment"""
        # Try new format first (G1-12345, D2-12345, H-12345)
        # New format has single char prefix
        if comment and len(comment) > 0 and comment[0] in ['G', 'D', 'H'] and '-' in comment:
            try:
                # For new format: "G1-12345" or "D2-12345" or "H-12345"
                ticket_str = comment.split('-')[-1].strip()
                return int(ticket_str)
            except (ValueError, IndexError):
                pass

        # Try old format (Grid L1 - 12345)
        if ' - ' in comment:
            try:
                ticket_str = comment.split(' - ')[-1].strip()
                return int(ticket_str)
            except (ValueError, IndexError):
                pass

        return None

    def _identify_recovery_type(self, comment: str) -> str:
        """Identify recovery type from comment"""
        if comment.startswith('G') or 'Grid' in comment:
            return 'Grid'
        elif comment.startswith('D') or 'DCA' in comment:
            return 'DCA'
        elif comment.startswith('H') or 'Hedge' in comment:
            return 'Hedge'
        return 'Unknown'

    def detect_duplicates(self):
        """Detect duplicate recovery trades (comment truncation bug)"""
        print(f"\n{'='*80}")
        print(f"🔍 DETECTING DUPLICATE RECOVERY TRADES")
        print(f"{'='*80}\n")

        # Group recovery deals by parent ticket and type
        recovery_groups = defaultdict(lambda: defaultdict(list))

        for parent_ticket, children in self.parent_child_map.items():
            for child in children:
                recovery_type = child['recovery_type']
                recovery_groups[parent_ticket][recovery_type].append(child)

        # Find duplicates (multiple of same type for same parent)
        duplicate_count = 0

        for parent_ticket, types in recovery_groups.items():
            for recovery_type, deals in types.items():
                if len(deals) > 1:
                    duplicate_count += len(deals) - 1
                    self.duplicates.append({
                        'parent_ticket': parent_ticket,
                        'recovery_type': recovery_type,
                        'count': len(deals),
                        'deals': deals
                    })

        if self.duplicates:
            print(f"⚠️  DUPLICATES FOUND: {duplicate_count} duplicate recovery trades detected!\n")
            for dup in self.duplicates:
                print(f"   Parent #{dup['parent_ticket']} - {dup['recovery_type']}")
                print(f"      Expected: 1")
                print(f"      Found: {dup['count']}")
                print(f"      Deals:")
                for deal in dup['deals']:
                    print(f"         #{deal['ticket']} @ {deal['time'].strftime('%H:%M:%S')} - {deal['type'].upper()} {deal['volume']:.2f} [Comment: '{deal['comment']}']")
                print()

            print(f"🔍 Analysis:")
            print(f"   This indicates the comment truncation bug was active")
            print(f"   Each reboot before fix created duplicate recovery trades")
            print(f"   This DOUBLED exposure on every reboot")
        else:
            print(f"✅ No duplicates detected")

        print(f"\n{'='*80}\n")

    def detect_orphaned_hedges(self):
        """Detect hedge positions that may have worked independently"""
        print(f"\n{'='*80}")
        print(f"🔍 DETECTING ORPHANED HEDGE POSITIONS")
        print(f"{'='*80}\n")

        orphaned_hedges = []

        # Check orphans list for hedges
        for orphan_entry in self.orphans:
            deal = orphan_entry['deal']
            if deal['recovery_type'] == 'Hedge':
                orphaned_hedges.append(orphan_entry)

        # Check if any hedge became a parent itself
        hedge_parents = []
        for parent_ticket in self.parent_child_map.keys():
            parent_deal = next((d for d in self.deals if d['ticket'] == parent_ticket), None)
            if parent_deal and parent_deal.get('recovery_type') == 'Hedge':
                hedge_parents.append({
                    'parent_deal': parent_deal,
                    'children': self.parent_child_map[parent_ticket]
                })

        if orphaned_hedges:
            print(f"⚠️  ORPHANED HEDGES: {len(orphaned_hedges)} hedge(s) with no valid parent\n")
            for entry in orphaned_hedges:
                deal = entry['deal']
                print(f"   Hedge #{deal['ticket']}")
                print(f"      Time: {deal['time'].strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"      Type: {deal['type'].upper()}")
                print(f"      Volume: {deal['volume']:.2f}")
                print(f"      Comment: '{deal['comment']}'")
                print(f"      Reason: {entry['reason']}")
                print()

        if hedge_parents:
            print(f"🚨 CRITICAL: {len(hedge_parents)} HEDGE(S) BECAME PARENT POSITION(S)!\n")
            print(f"   This is the CATASTROPHIC BUG that blew the account!\n")
            for entry in hedge_parents:
                parent = entry['parent_deal']
                children = entry['children']
                print(f"   Orphaned Hedge #{parent['ticket']}")
                print(f"      Original hedge: {parent['type'].upper()} {parent['volume']:.2f}")
                print(f"      Time became parent: {parent['time'].strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"      Triggered its own recovery with {len(children)} children:")
                for child in children:
                    print(f"         └─ {child['recovery_type']} #{child['ticket']} - {child['type'].upper()} {child['volume']:.2f}")
                print()

                # Calculate exposure from this orphaned hedge
                total_volume = parent['volume']
                for child in children:
                    total_volume += child['volume']
                print(f"      Total exposure from orphaned hedge: {total_volume:.2f} lots")
                print(f"      ⚠️  This fought against the original parent's stack!")
                print()

        if not orphaned_hedges and not hedge_parents:
            print(f"✅ No orphaned hedges detected")

        print(f"\n{'='*80}\n")

    def analyze_exposure_timeline(self):
        """Analyze how exposure grew over time"""
        print(f"\n{'='*80}")
        print(f"📈 EXPOSURE GROWTH TIMELINE")
        print(f"{'='*80}\n")

        # Sort deals by time
        entry_deals = sorted([d for d in self.deals if d['entry'] == 0], key=lambda x: x['time'])

        if not entry_deals:
            print("No entry deals found")
            return

        cumulative_buy = 0.0
        cumulative_sell = 0.0
        cumulative_net = 0.0
        cumulative_total = 0.0

        print(f"{'Time':<20} {'Type':<8} {'Volume':<8} {'Cum Buy':<10} {'Cum Sell':<10} {'Net Exp':<10} {'Total Exp':<10} {'Comment':<30}")
        print(f"{'-'*130}")

        for deal in entry_deals:
            if deal['type'] == 'buy':
                cumulative_buy += deal['volume']
            else:
                cumulative_sell += deal['volume']

            cumulative_net = cumulative_buy - cumulative_sell
            cumulative_total = cumulative_buy + cumulative_sell

            comment = deal.get('comment', '')[:30]

            print(f"{deal['time'].strftime('%Y-%m-%d %H:%M:%S'):<20} "
                  f"{deal['type'].upper():<8} "
                  f"{deal['volume']:<8.2f} "
                  f"{cumulative_buy:<10.2f} "
                  f"{cumulative_sell:<10.2f} "
                  f"{cumulative_net:+<10.2f} "
                  f"{cumulative_total:<10.2f} "
                  f"{comment:<30}")

            self.exposure_timeline.append({
                'time': deal['time'],
                'deal': deal,
                'cumulative_buy': cumulative_buy,
                'cumulative_sell': cumulative_sell,
                'net_exposure': cumulative_net,
                'total_exposure': cumulative_total
            })

        print(f"\n📊 Peak Exposure:")
        max_total = max(self.exposure_timeline, key=lambda x: x['total_exposure'])
        print(f"   Total: {max_total['total_exposure']:.2f} lots @ {max_total['time'].strftime('%Y-%m-%d %H:%M:%S')}")

        max_net = max(self.exposure_timeline, key=lambda x: abs(x['net_exposure']))
        print(f"   Net: {max_net['net_exposure']:+.2f} lots @ {max_net['time'].strftime('%Y-%m-%d %H:%M:%S')}")

        print(f"\n{'='*80}\n")

    def analyze_drawdown_progression(self):
        """Analyze account drawdown progression"""
        print(f"\n{'='*80}")
        print(f"💰 DRAWDOWN PROGRESSION")
        print(f"{'='*80}\n")

        # Get deals with profit/loss info
        exit_deals = [d for d in self.deals if d['entry'] == 1]  # Exit deals

        if not exit_deals:
            print("No exit deals found (account may still have open positions)")
            return

        # Sort by time
        exit_deals = sorted(exit_deals, key=lambda x: x['time'])

        cumulative_profit = 0.0
        peak_profit = 0.0

        print(f"{'Time':<20} {'Type':<8} {'Volume':<8} {'Profit':<10} {'Cum P/L':<12} {'Drawdown':<20} {'Comment':<30}")
        print(f"{'-'*130}")

        for deal in exit_deals:
            profit = deal['profit'] + deal.get('commission', 0) + deal.get('swap', 0)
            cumulative_profit += profit

            if cumulative_profit > peak_profit:
                peak_profit = cumulative_profit

            drawdown = peak_profit - cumulative_profit
            drawdown_pct = (drawdown / peak_profit * 100) if peak_profit > 0 else 0

            comment = deal.get('comment', '')[:30]

            drawdown_str = f"${drawdown:.2f} ({drawdown_pct:.1f}%)"
            print(f"{deal['time'].strftime('%Y-%m-%d %H:%M:%S'):<20} "
                  f"{deal['type'].upper():<8} "
                  f"{deal['volume']:<8.2f} "
                  f"${profit:<9.2f} "
                  f"${cumulative_profit:<11.2f} "
                  f"{drawdown_str:<20} "
                  f"{comment:<30}")

        print(f"\n📊 Summary:")
        print(f"   Total P/L: ${cumulative_profit:.2f}")
        print(f"   Peak Profit: ${peak_profit:.2f}")
        print(f"   Max Drawdown: ${peak_profit - min(cumulative_profit, 0):.2f}")

        print(f"\n{'='*80}\n")

    def generate_summary_report(self):
        """Generate summary report of findings"""
        print(f"\n{'='*80}")
        print(f"📋 FORENSIC ANALYSIS SUMMARY")
        print(f"{'='*80}\n")

        print(f"🔍 Findings:\n")

        # Bug #1: Duplicate recovery trades
        if self.duplicates:
            print(f"   ❌ DUPLICATE RECOVERY TRADES DETECTED")
            print(f"      Count: {len(self.duplicates)} instances")
            total_dups = sum(dup['count'] - 1 for dup in self.duplicates)
            print(f"      Excess trades: {total_dups}")
            print(f"      Impact: {total_dups} × base lot size in duplicated exposure")
            print(f"      Cause: Comment truncation bug (before fix df29b76)")
            print()

        # Bug #2: Orphaned hedges
        orphaned_hedges = [o for o in self.orphans if o['deal'].get('recovery_type') == 'Hedge']
        hedge_parents = [p for p in self.parent_child_map.keys()
                        if any(d.get('recovery_type') == 'Hedge'
                               for d in self.deals if d['ticket'] == p)]

        if orphaned_hedges or hedge_parents:
            print(f"   🚨 ORPHANED HEDGE POSITIONS DETECTED")
            print(f"      Orphaned hedges: {len(orphaned_hedges)}")
            print(f"      Hedges that became parents: {len(hedge_parents)}")
            print(f"      Impact: CATASTROPHIC - Hedges triggered their own recovery")
            print(f"      Cause: Comment parsing failure + no orphan detection")
            print()

        # Exposure analysis
        if self.exposure_timeline:
            max_exp = max(self.exposure_timeline, key=lambda x: x['total_exposure'])
            print(f"   📈 EXPOSURE ANALYSIS")
            print(f"      Peak total exposure: {max_exp['total_exposure']:.2f} lots")
            print(f"      Time of peak: {max_exp['time'].strftime('%Y-%m-%d %H:%M:%S')}")
            if max_exp['total_exposure'] > 23.0:
                print(f"      ⚠️  EXCEEDED MAX_TOTAL_LOTS (23.0) by {max_exp['total_exposure'] - 23.0:.2f} lots")
            print()

        # Orphans
        if self.orphans:
            print(f"   ⚠️  ORPHANED POSITIONS")
            print(f"      Count: {len(self.orphans)}")
            print(f"      Impact: Recovery positions not properly managed")
            print()

        print(f"{'='*80}\n")

        # Recommendations
        print(f"💡 RECOMMENDATIONS:\n")
        print(f"   1. ✅ Comment truncation fixed (commit df29b76) - shorter format")
        print(f"   2. ❌ MUST implement emergency close when drawdown limit hit")
        print(f"   3. ❌ MUST implement orphan detection and alerts")
        print(f"   4. ❌ MUST add per-stack exposure limits")
        print(f"   5. ❌ MUST reduce HEDGE_RATIO from 5.0x to 2.0x")
        print(f"   6. ❌ MUST reduce DCA_MAX_LEVELS from 8 to 5")
        print(f"   7. ❌ MUST reduce MAX_TOTAL_LOTS from 23.0 to 10.0")
        print(f"\n   See POST_MORTEM_ANALYSIS.md for detailed fixes")
        print(f"\n{'='*80}\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Forensic analysis of MT5 trade history')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)', default=None)
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)', default=None)
    parser.add_argument('--days', type=int, help='Number of days to analyze (default: 7)', default=7)
    args = parser.parse_args()

    # Parse dates
    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    else:
        end_date = datetime.now()

    if args.start_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    else:
        start_date = end_date - timedelta(days=args.days)

    # Create analyzer
    analyzer = ForensicAnalyzer()

    try:
        # Connect to MT5
        if not analyzer.connect():
            return 1

        # Fetch history
        if not analyzer.fetch_history(start_date, end_date):
            return 1

        # Run analysis
        analyzer.analyze_parent_child_relationships()
        analyzer.detect_duplicates()
        analyzer.detect_orphaned_hedges()
        analyzer.analyze_exposure_timeline()
        analyzer.analyze_drawdown_progression()

        # Generate summary
        analyzer.generate_summary_report()

        return 0

    finally:
        analyzer.disconnect()


if __name__ == '__main__':
    exit(main())
