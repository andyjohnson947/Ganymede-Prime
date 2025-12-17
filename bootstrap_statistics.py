#!/usr/bin/env python3
"""
Bootstrap Recovery Stack Statistics from Historical Trade Data

This script analyzes historical MT5 trades to calculate baseline statistics
for adaptive risk management. Run once to bootstrap, then bot maintains stats.

Usage:
    python bootstrap_statistics.py [--days 60] [--output stats.json]
"""

import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

from trading_bot.core.mt5_manager import MT5Manager
from trading_bot.config.config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER


def parse_comment(comment: str) -> tuple[bool, Optional[int]]:
    """
    Parse trade comment to identify recovery trades and parent ticket

    Returns:
        Tuple of (is_recovery, parent_ticket)
    """
    if not comment:
        return False, None

    # New format: G1-12345, D2-12345, H-12345
    if '-' in comment and any(comment.startswith(prefix) for prefix in ['G', 'D', 'H']):
        try:
            parent_ticket = int(comment.split('-')[-1])
            return True, parent_ticket
        except (ValueError, IndexError):
            pass

    # Old format: Grid L1 - 12345, DCA L2 - 12345, Hedge - 12345
    if ' - ' in comment and any(keyword in comment for keyword in ['Grid', 'DCA', 'Hedge']):
        try:
            parent_ticket = int(comment.split(' - ')[-1])
            return True, parent_ticket
        except (ValueError, IndexError):
            pass

    return False, None


def group_trades_into_stacks(deals: List[Dict]) -> Dict[int, Dict]:
    """
    Group historical trades into parent + recovery stacks

    Args:
        deals: List of closed deals from MT5 history

    Returns:
        Dict mapping parent_ticket -> stack_data
    """
    stacks = {}
    recovery_trades = defaultdict(list)

    # First pass: identify parent positions and recovery trades
    for deal in deals:
        if deal['entry'] != 1:  # 1 = DEAL_ENTRY_OUT (close)
            continue

        ticket = deal['position_id']
        comment = deal.get('comment', '')

        is_recovery, parent_ticket = parse_comment(comment)

        if is_recovery and parent_ticket:
            # This is a recovery trade
            recovery_trades[parent_ticket].append(deal)
        else:
            # This is a parent position
            if ticket not in stacks:
                stacks[ticket] = {
                    'parent_deal': deal,
                    'recovery_deals': [],
                    'open_time': datetime.fromtimestamp(deal['time']),
                }

    # Second pass: link recovery trades to parents
    for parent_ticket, recoveries in recovery_trades.items():
        if parent_ticket in stacks:
            stacks[parent_ticket]['recovery_deals'].extend(recoveries)

    return stacks


def calculate_stack_metrics(stack: Dict, deals: List[Dict]) -> Optional[Dict]:
    """
    Calculate metrics for a closed stack

    Args:
        stack: Stack data (parent + recovery deals)
        deals: All deals (for finding open entries)

    Returns:
        Dict with stack metrics or None if insufficient data
    """
    parent_deal = stack['parent_deal']
    recovery_deals = stack['recovery_deals']

    # Find entry deals (DEAL_ENTRY_IN = 0)
    parent_ticket = parent_deal['position_id']
    entry_deals = [d for d in deals if d['position_id'] == parent_ticket and d['entry'] == 0]

    if not entry_deals:
        return None

    # Calculate metrics
    parent_entry = entry_deals[0]
    open_time = datetime.fromtimestamp(parent_entry['time'])
    close_time = datetime.fromtimestamp(parent_deal['time'])
    duration_minutes = (close_time - open_time).total_seconds() / 60

    # Calculate total volume (parent + all recovery)
    total_volume = parent_entry['volume']
    for recovery in recovery_deals:
        recovery_entries = [d for d in deals if d['position_id'] == recovery['position_id'] and d['entry'] == 0]
        if recovery_entries:
            total_volume += recovery_entries[0]['volume']

    # Calculate total P&L (parent + all recovery)
    total_pnl = parent_deal['profit']
    for recovery in recovery_deals:
        total_pnl += recovery['profit']

    # Calculate max drawdown (approximate from final P&L if negative)
    # Note: This is an approximation - actual max drawdown during position lifetime
    # would need tick data. We use final P&L as proxy for closed losers.
    max_drawdown = abs(min(total_pnl, 0))

    # Count recovery depth
    recovery_depth = len(recovery_deals)

    # Estimate max underwater pips (rough calculation)
    entry_price = parent_entry['price']
    # For closed losers, estimate pips from loss
    # Assuming $10 per pip per lot (approximate for major pairs)
    if total_pnl < 0 and total_volume > 0:
        estimated_pip_value = 10.0  # $10 per pip per lot (rough estimate)
        max_underwater_pips = abs(total_pnl) / (total_volume * estimated_pip_value)
    else:
        max_underwater_pips = 0

    return {
        'ticket': parent_ticket,
        'symbol': parent_deal['symbol'],
        'open_time': open_time.isoformat(),
        'close_time': close_time.isoformat(),
        'duration_minutes': duration_minutes,
        'max_volume': total_volume,
        'max_drawdown': max_drawdown,
        'max_underwater_pips': max_underwater_pips,
        'recovery_depth': recovery_depth,
        'final_pnl': total_pnl,
    }


def bootstrap_statistics(days: int = 60, magic_number: Optional[int] = None) -> Dict:
    """
    Bootstrap statistics from MT5 trade history

    Args:
        days: Number of days of history to analyze
        magic_number: Filter by magic number (None = all trades)

    Returns:
        Dict with statistics
    """
    print(f"🔍 Analyzing last {days} days of trade history...")
    print(f"{'='*80}\n")

    # Initialize MT5
    mt5 = MT5Manager(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
    if not mt5.connect():
        print("❌ Failed to connect to MT5")
        return {}

    # Get historical deals
    date_from = datetime.now() - timedelta(days=days)

    print(f"📊 Fetching deals from {date_from.strftime('%Y-%m-%d')}...")
    deals = mt5.get_history_deals(date_from=date_from, date_to=datetime.now())

    if not deals:
        print("❌ No historical deals found")
        mt5.disconnect()
        return {}

    print(f"✅ Found {len(deals)} deals\n")

    # Filter by magic number if specified
    if magic_number is not None:
        deals = [d for d in deals if d.get('magic', 0) == magic_number]
        print(f"🔍 Filtered to {len(deals)} deals with magic number {magic_number}\n")

    # Group into stacks
    print("📦 Grouping trades into recovery stacks...")
    stacks = group_trades_into_stacks(deals)
    print(f"✅ Found {len(stacks)} parent positions\n")

    # Calculate metrics for each stack
    print("📈 Calculating stack metrics...")
    stack_metrics = []

    for ticket, stack in stacks.items():
        metrics = calculate_stack_metrics(stack, deals)
        if metrics:
            stack_metrics.append(metrics)

    print(f"✅ Calculated metrics for {len(stack_metrics)} stacks\n")

    if not stack_metrics:
        print("⚠️  No valid stacks found for analysis")
        mt5.disconnect()
        return {}

    # Calculate statistics
    print(f"{'='*80}")
    print("📊 STATISTICS SUMMARY")
    print(f"{'='*80}\n")

    drawdowns = [s['max_drawdown'] for s in stack_metrics]
    volumes = [s['max_volume'] for s in stack_metrics]
    durations = [s['duration_minutes'] for s in stack_metrics]
    pips = [s['max_underwater_pips'] for s in stack_metrics]
    depths = [s['recovery_depth'] for s in stack_metrics]
    pnls = [s['final_pnl'] for s in stack_metrics]

    def calc_stats(values):
        if not values:
            return {'mean': 0, 'min': 0, 'max': 0}
        return {
            'mean': sum(values) / len(values),
            'min': min(values),
            'max': max(values),
        }

    statistics = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'days_analyzed': days,
            'total_stacks': len(stack_metrics),
            'magic_number': magic_number,
        },
        'drawdown': calc_stats(drawdowns),
        'volume': calc_stats(volumes),
        'duration_minutes': calc_stats(durations),
        'underwater_pips': calc_stats(pips),
        'recovery_depth': calc_stats(depths),
        'final_pnl': calc_stats(pnls),
        'closed_stack_history': stack_metrics[-30:],  # Keep last 30 for rolling average
    }

    print(f"Total stacks analyzed: {len(stack_metrics)}")
    print(f"\nDrawdown (unrealized loss):")
    print(f"  Average: ${statistics['drawdown']['mean']:.2f}")
    print(f"  Min: ${statistics['drawdown']['min']:.2f}")
    print(f"  Max: ${statistics['drawdown']['max']:.2f}")

    print(f"\nVolume (max exposure):")
    print(f"  Average: {statistics['volume']['mean']:.2f} lots")
    print(f"  Min: {statistics['volume']['min']:.2f} lots")
    print(f"  Max: {statistics['volume']['max']:.2f} lots")

    print(f"\nDuration:")
    print(f"  Average: {statistics['duration_minutes']['mean']:.1f} minutes ({statistics['duration_minutes']['mean']/60:.1f} hours)")
    print(f"  Min: {statistics['duration_minutes']['min']:.1f} minutes")
    print(f"  Max: {statistics['duration_minutes']['max']:.1f} minutes ({statistics['duration_minutes']['max']/60:.1f} hours)")

    print(f"\nMax underwater pips:")
    print(f"  Average: {statistics['underwater_pips']['mean']:.1f} pips")
    print(f"  Min: {statistics['underwater_pips']['min']:.1f} pips")
    print(f"  Max: {statistics['underwater_pips']['max']:.1f} pips")

    print(f"\nRecovery depth (Grid+Hedge+DCA count):")
    print(f"  Average: {statistics['recovery_depth']['mean']:.1f} trades")
    print(f"  Min: {statistics['recovery_depth']['min']} trades")
    print(f"  Max: {statistics['recovery_depth']['max']} trades")

    print(f"\nFinal P&L:")
    print(f"  Average: ${statistics['final_pnl']['mean']:.2f}")
    print(f"  Total: ${sum(pnls):.2f}")

    # Calculate adaptive thresholds
    avg_drawdown = statistics['drawdown']['mean']
    hyper_care_threshold = avg_drawdown * 1.25
    auto_close_threshold = avg_drawdown * 1.35

    print(f"\n{'='*80}")
    print("🎯 ADAPTIVE THRESHOLDS")
    print(f"{'='*80}\n")
    print(f"Average drawdown: ${avg_drawdown:.2f}")
    print(f"Hyper care threshold (125%): ${hyper_care_threshold:.2f}")
    print(f"Auto-close threshold (135%): ${auto_close_threshold:.2f}")

    print(f"\n{'='*80}\n")

    mt5.disconnect()
    return statistics


def main():
    parser = argparse.ArgumentParser(description='Bootstrap recovery stack statistics from MT5 history')
    parser.add_argument('--days', type=int, default=60, help='Number of days of history to analyze (default: 60)')
    parser.add_argument('--magic', type=int, default=None, help='Filter by magic number (default: all trades)')
    parser.add_argument('--output', type=str, default='recovery_stack_statistics.json', help='Output file (default: recovery_stack_statistics.json)')

    args = parser.parse_args()

    # Bootstrap statistics
    statistics = bootstrap_statistics(days=args.days, magic_number=args.magic)

    if not statistics:
        print("❌ Failed to generate statistics")
        return 1

    # Save to file
    output_path = args.output
    with open(output_path, 'w') as f:
        json.dump(statistics, f, indent=2)

    print(f"✅ Statistics saved to: {output_path}")
    print(f"\nNext steps:")
    print(f"1. Review the statistics above")
    print(f"2. Adjust thresholds in strategy_config.py if needed")
    print(f"3. Run the bot - it will load {output_path} on startup")

    return 0


if __name__ == '__main__':
    exit(main())
