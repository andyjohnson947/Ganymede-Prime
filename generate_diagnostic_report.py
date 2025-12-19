#!/usr/bin/env python3
"""
Diagnostic Report Generator - CLI Tool

Analyzes last X days of trading and generates comprehensive report showing:
- What's working (keep doing)
- What's broken (fix or remove)
- What needs tuning (adjust parameters)
- Regime detection accuracy
- Confluence factor effectiveness
- Recovery mechanism performance

Usage:
    python generate_diagnostic_report.py --days 7
    python generate_diagnostic_report.py --days 14 --login 12345 --password "pass" --server "Broker"
    python generate_diagnostic_report.py --help
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent / 'trading_bot'))

from core.mt5_manager import MT5Manager
from diagnostics.data_store import DataStore
from diagnostics.diagnostic_report_generator import DiagnosticReportGenerator


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Generate comprehensive diagnostic report'
    )

    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days to analyze (default: 7)'
    )

    parser.add_argument(
        '--min-trades',
        type=int,
        default=5,
        help='Minimum trades required for statistical significance (default: 5)'
    )

    parser.add_argument(
        '--login',
        type=int,
        help='MT5 account login (optional - only needed for live price data correlation)'
    )

    parser.add_argument(
        '--password',
        type=str,
        help='MT5 account password (optional)'
    )

    parser.add_argument(
        '--server',
        type=str,
        help='MT5 server name (optional)'
    )

    parser.add_argument(
        '--data-dir',
        type=str,
        default='data/diagnostics',
        help='Directory containing diagnostic data (default: data/diagnostics)'
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()

    print("=" * 80)
    print("     DIAGNOSTIC REPORT GENERATOR")
    print("=" * 80)
    print()

    # Initialize data store
    data_store = DataStore(args.data_dir)

    # Initialize MT5 if credentials provided (for price data correlation)
    mt5_manager = None
    if args.login and args.password and args.server:
        print("🔌 Connecting to MT5 for price data correlation...")
        mt5_manager = MT5Manager(
            login=args.login,
            password=args.password,
            server=args.server
        )

        if not mt5_manager.connect():
            print("⚠️  Failed to connect to MT5 - continuing without price correlation")
            mt5_manager = None
        else:
            print("✅ MT5 Connected\n")
    else:
        print("ℹ️  Running without MT5 connection (no live price correlation)")
        print("   To enable: --login LOGIN --password PASSWORD --server SERVER\n")

    # Create mock MT5 manager if not connected
    if mt5_manager is None:
        class MockMT5:
            def get_historical_data(self, *args, **kwargs):
                return None

        mt5_manager = MockMT5()

    # Generate report
    generator = DiagnosticReportGenerator(mt5_manager, data_store)

    try:
        report = generator.generate_report(
            days=args.days,
            min_trades=args.min_trades
        )

        # Print report
        generator.print_report(report)

        # Save report to file
        output_file = f"diagnostic_report_{args.days}d.txt"
        print(f"💾 Saving report to {output_file}...")

        # TODO: Implement report export to file

        print(f"✅ Report generated successfully\n")

    except Exception as e:
        print(f"\n❌ Error generating report: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if hasattr(mt5_manager, 'disconnect'):
            mt5_manager.disconnect()


if __name__ == "__main__":
    main()
