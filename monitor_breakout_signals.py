#!/usr/bin/env python3
"""
Continuous Breakout Signal Monitor
Runs breakout detector periodically and logs all signals/conditions

Usage:
    python monitor_breakout_signals.py <login> <password> <server> [symbols] [interval_minutes]

Example:
    python monitor_breakout_signals.py 12345 yourpass "VantageInternational-Demo" EURUSD,GBPUSD 60

This will monitor EURUSD and GBPUSD every 60 minutes and log all findings.
"""

import MetaTrader5 as mt5
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime, timedelta
import time
import json

# Add paths
sys.path.insert(0, str(Path(__file__).parent))

from breakout_strategy.strategies.breakout_detector import BreakoutDetector
from breakout_strategy.indicators.volume_analyzer import VolumeAnalyzer, format_volume_summary
from trading_bot.indicators.vwap import VWAP
from trading_bot.indicators.volume_profile import VolumeProfile


class BreakoutMonitor:
    """Continuous monitoring of breakout signals"""

    def __init__(self, login: int, password: str, server: str, symbols: list, interval_minutes: int = 60):
        self.login = login
        self.password = password
        self.server = server
        self.symbols = symbols
        self.interval_minutes = interval_minutes
        self.log_dir = Path(__file__).parent / "logs" / "breakout_monitoring"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.detector = BreakoutDetector()
        self.volume_analyzer = VolumeAnalyzer(lookback=20)

        # Stats tracking
        self.stats = {
            'scans_performed': 0,
            'signals_detected': 0,
            'last_signal_time': None,
            'start_time': datetime.now(),
        }

    def connect_mt5(self) -> bool:
        """Connect to MT5"""
        if not mt5.initialize():
            self.log_error("Failed to initialize MT5")
            return False

        if not mt5.login(self.login, password=self.password, server=self.server):
            error = mt5.last_error()
            self.log_error(f"Login failed: {error}")
            mt5.shutdown()
            return False

        return True

    def disconnect_mt5(self):
        """Disconnect from MT5"""
        mt5.shutdown()

    def fetch_market_data(self, symbol: str) -> dict:
        """Fetch all required market data for a symbol"""
        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            # Try alternatives
            for alt in [f"{symbol}.a", f"{symbol}m", f"{symbol}-sb"]:
                symbol_info = mt5.symbol_info(alt)
                if symbol_info:
                    symbol = alt
                    break
            else:
                return None

        # Fetch H1 data (primary timeframe)
        h1_data = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 200)
        daily_data = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 50)
        weekly_data = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_W1, 0, 20)

        if h1_data is None or daily_data is None or weekly_data is None:
            return None

        # Convert to DataFrames
        h1_df = pd.DataFrame(h1_data)
        daily_df = pd.DataFrame(daily_data)
        weekly_df = pd.DataFrame(weekly_data)

        # Add time column
        h1_df['time'] = pd.to_datetime(h1_df['time'], unit='s')
        daily_df['time'] = pd.to_datetime(daily_df['time'], unit='s')
        weekly_df['time'] = pd.to_datetime(weekly_df['time'], unit='s')

        # Calculate indicators
        vwap_calculator = VWAP()
        h1_df = vwap_calculator.calculate(h1_df)

        vp_calculator = VolumeProfile()
        vp_data = vp_calculator.calculate(h1_df)

        # Add volume profile data as columns
        if vp_data and 'poc' in vp_data:
            h1_df['volume_poc'] = vp_data['poc']
            h1_df['volume_vah'] = vp_data['vah']
            h1_df['volume_val'] = vp_data['val']
            if 'lvn_price' in vp_data:
                h1_df['lvn_price'] = vp_data['lvn_price']
                h1_df['lvn_percentile'] = vp_data.get('lvn_percentile', 50)

        return {
            'symbol': symbol,
            'symbol_info': symbol_info,
            'h1_df': h1_df,
            'daily_df': daily_df,
            'weekly_df': weekly_df,
        }

    def scan_symbol(self, symbol: str) -> dict:
        """Scan a single symbol for breakout signals"""
        market_data = self.fetch_market_data(symbol)
        if not market_data:
            return {
                'symbol': symbol,
                'error': 'Failed to fetch market data',
                'timestamp': datetime.now().isoformat(),
            }

        h1_df = market_data['h1_df']
        daily_df = market_data['daily_df']
        weekly_df = market_data['weekly_df']
        symbol_info = market_data['symbol_info']

        # Get volume summary
        volume_summary = self.volume_analyzer.get_volume_summary(h1_df)

        # Detect breakout signal
        signal = self.detector.detect_breakout(
            current_data=h1_df,
            daily_data=daily_df,
            weekly_data=weekly_df,
            symbol=market_data['symbol']
        )

        # Build result
        latest = h1_df.iloc[-1]
        result = {
            'symbol': market_data['symbol'],
            'timestamp': datetime.now().isoformat(),
            'current_price': {
                'bid': symbol_info.bid,
                'ask': symbol_info.ask,
                'close': float(latest['close']),
            },
            'volume': {
                'percentile': volume_summary['percentile'],
                'ratio': volume_summary['volume_ratio'],
                'trend': volume_summary['volume_trend'],
                'validation': volume_summary['breakout_validation']['recommendation'],
                'quality': volume_summary['breakout_validation']['quality'],
            },
            'indicators': {},
            'signal': None,
        }

        # Add indicator values
        if 'adx' in h1_df.columns:
            result['indicators']['adx'] = float(latest['adx'])

        if 'vwap' in h1_df.columns:
            price = latest['close']
            vwap = latest['vwap']
            vwap_dist_pct = abs(price - vwap) / vwap * 100
            result['indicators']['vwap_distance_pct'] = vwap_dist_pct
            result['indicators']['above_vwap'] = price > vwap

        if 'lvn_percentile' in h1_df.columns and not pd.isna(latest['lvn_percentile']):
            result['indicators']['lvn_percentile'] = float(latest['lvn_percentile'])

        # Add signal if detected
        if signal:
            result['signal'] = {
                'direction': signal['direction'],
                'entry_type': signal['entry_type'],
                'entry_price': signal['entry_price'],
                'stop_loss': signal['stop_loss'],
                'take_profit': signal['take_profit'],
                'confluence_score': signal['confluence_score'],
                'factors': signal['factors'],
            }

            # Calculate R:R
            if signal['stop_loss'] and signal['take_profit']:
                risk = abs(signal['entry_price'] - signal['stop_loss'])
                reward = abs(signal['take_profit'] - signal['entry_price'])
                result['signal']['risk_reward'] = reward / risk if risk > 0 else 0

        return result

    def scan_all_symbols(self) -> list:
        """Scan all configured symbols"""
        results = []

        if not self.connect_mt5():
            return results

        try:
            for symbol in self.symbols:
                result = self.scan_symbol(symbol)
                results.append(result)

                # Log signal if detected
                if result.get('signal'):
                    self.log_signal(result)
                    self.stats['signals_detected'] += 1
                    self.stats['last_signal_time'] = datetime.now()

            self.stats['scans_performed'] += 1

        finally:
            self.disconnect_mt5()

        return results

    def log_signal(self, result: dict):
        """Log a detected signal"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.log_dir / f"signal_{timestamp}_{result['symbol']}.json"

        with open(log_file, 'w') as f:
            json.dump(result, f, indent=2)

        # Also append to signals summary
        summary_file = self.log_dir / "signals_summary.log"
        with open(summary_file, 'a') as f:
            signal = result['signal']
            f.write(f"\n{'='*80}\n")
            f.write(f"🚀 SIGNAL DETECTED: {result['symbol']} - {timestamp}\n")
            f.write(f"{'='*80}\n")
            f.write(f"Direction: {signal['direction'].upper()}\n")
            f.write(f"Entry Type: {signal['entry_type']}\n")
            f.write(f"Entry Price: {signal['entry_price']:.5f}\n")
            f.write(f"Stop Loss: {signal['stop_loss']:.5f}\n")
            f.write(f"Take Profit: {signal['take_profit']:.5f}\n")
            f.write(f"Risk/Reward: 1:{signal['risk_reward']:.2f}\n")
            f.write(f"Confluence Score: {signal['confluence_score']}\n")
            f.write(f"Factors: {', '.join(signal['factors'])}\n")
            f.write(f"\nCurrent Price: {result['current_price']['close']:.5f}\n")
            f.write(f"ADX: {result['indicators'].get('adx', 'N/A')}\n")
            f.write(f"VWAP Distance: {result['indicators'].get('vwap_distance_pct', 'N/A'):.2f}%\n")
            f.write(f"Volume: {result['volume']['percentile']:.0f}th percentile ({result['volume']['quality']})\n")
            f.write(f"\n")

    def log_scan_summary(self, results: list):
        """Log summary of scan results"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary_file = self.log_dir / "scan_history.log"

        with open(summary_file, 'a') as f:
            f.write(f"\n[{timestamp}] Scan #{self.stats['scans_performed']}\n")
            f.write(f"Symbols: {len(results)}\n")

            for result in results:
                if 'error' in result:
                    f.write(f"  {result['symbol']}: ERROR - {result['error']}\n")
                    continue

                signal_status = "🚀 SIGNAL" if result.get('signal') else "⏸️  No signal"

                adx = result['indicators'].get('adx', 'N/A')
                adx_str = f"{adx:.1f}" if isinstance(adx, float) else str(adx)

                vwap_dist = result['indicators'].get('vwap_distance_pct', 'N/A')
                vwap_str = f"{vwap_dist:.2f}%" if isinstance(vwap_dist, float) else str(vwap_dist)

                lvn = result['indicators'].get('lvn_percentile', 'N/A')
                lvn_str = f"{lvn:.0f}th" if isinstance(lvn, float) else str(lvn)

                vol_pct = result['volume']['percentile']

                f.write(f"  {result['symbol']}: {signal_status} | ")
                f.write(f"ADX={adx_str} | VWAP Dist={vwap_str} | ")
                f.write(f"LVN={lvn_str} | Vol={vol_pct:.0f}th ({result['volume']['quality']})\n")

                if result.get('signal'):
                    signal = result['signal']
                    f.write(f"    → {signal['direction'].upper()} @ {signal['entry_price']:.5f} | ")
                    f.write(f"Score: {signal['confluence_score']} | R:R 1:{signal['risk_reward']:.2f}\n")

    def log_error(self, message: str):
        """Log an error"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_file = self.log_dir / "errors.log"

        with open(error_file, 'a') as f:
            f.write(f"[{timestamp}] ERROR: {message}\n")

    def print_status(self, results: list):
        """Print current status to console"""
        print("\n" + "="*80)
        print(f"BREAKOUT MONITOR - Scan #{self.stats['scans_performed']}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)

        for result in results:
            if 'error' in result:
                print(f"\n❌ {result['symbol']}: {result['error']}")
                continue

            print(f"\n📊 {result['symbol']}")
            print(f"   Price: {result['current_price']['close']:.5f}")

            if 'adx' in result['indicators']:
                adx = result['indicators']['adx']
                print(f"   ADX: {adx:.1f}", end="")
                if adx < 25:
                    print(" (Ranging)")
                elif adx >= 40:
                    print(" (Very strong trend)")
                else:
                    print(" (Trending)")
            else:
                print("   ADX: Not available")

            if 'vwap_distance_pct' in result['indicators']:
                vwap_dist = result['indicators']['vwap_distance_pct']
                above = result['indicators']['above_vwap']
                print(f"   VWAP Distance: {vwap_dist:.2f}% ({'Above' if above else 'Below'})")

            if 'lvn_percentile' in result['indicators']:
                lvn = result['indicators']['lvn_percentile']
                print(f"   LVN Percentile: {lvn:.0f}th")

            vol = result['volume']
            print(f"   Volume: {vol['percentile']:.0f}th percentile ({vol['quality']}) - {vol['validation']}")

            if result.get('signal'):
                signal = result['signal']
                print(f"\n   🚀 SIGNAL DETECTED!")
                print(f"      Direction: {signal['direction'].upper()}")
                print(f"      Entry: {signal['entry_price']:.5f}")
                print(f"      SL: {signal['stop_loss']:.5f} | TP: {signal['take_profit']:.5f}")
                print(f"      R:R 1:{signal['risk_reward']:.2f}")
                print(f"      Score: {signal['confluence_score']} | Factors: {', '.join(signal['factors'])}")
            else:
                print(f"   ⏸️  No signal")

        # Print overall stats
        runtime = datetime.now() - self.stats['start_time']
        print(f"\n{'='*80}")
        print(f"Total Scans: {self.stats['scans_performed']}")
        print(f"Total Signals: {self.stats['signals_detected']}")
        if self.stats['last_signal_time']:
            print(f"Last Signal: {self.stats['last_signal_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Runtime: {str(runtime).split('.')[0]}")
        print(f"Next scan in {self.interval_minutes} minutes")
        print(f"Logs: {self.log_dir}")
        print("="*80)

    def run(self):
        """Run continuous monitoring"""
        print("\n" + "="*80)
        print("BREAKOUT DETECTOR - CONTINUOUS MONITORING")
        print("="*80)
        print(f"Server: {self.server}")
        print(f"Symbols: {', '.join(self.symbols)}")
        print(f"Scan Interval: {self.interval_minutes} minutes")
        print(f"Log Directory: {self.log_dir}")
        print("\nPress Ctrl+C to stop monitoring")
        print("="*80)

        try:
            while True:
                # Perform scan
                results = self.scan_all_symbols()

                # Log results
                self.log_scan_summary(results)

                # Print to console
                self.print_status(results)

                # Wait for next interval
                time.sleep(self.interval_minutes * 60)

        except KeyboardInterrupt:
            print("\n\n" + "="*80)
            print("MONITORING STOPPED")
            print("="*80)
            runtime = datetime.now() - self.stats['start_time']
            print(f"Total Runtime: {str(runtime).split('.')[0]}")
            print(f"Total Scans: {self.stats['scans_performed']}")
            print(f"Total Signals: {self.stats['signals_detected']}")
            print(f"Logs saved to: {self.log_dir}")
            print("="*80 + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python monitor_breakout_signals.py <login> <password> <server> [symbols] [interval_minutes]")
        print()
        print("Examples:")
        print("  python monitor_breakout_signals.py 12345 yourpass 'VantageInternational-Demo' EURUSD 60")
        print("  python monitor_breakout_signals.py 12345 yourpass 'VantageInternational-Demo' 'EURUSD,GBPUSD,USDJPY' 30")
        print()
        print("Default symbols: EURUSD")
        print("Default interval: 60 minutes")
        sys.exit(1)

    login = int(sys.argv[1])
    password = sys.argv[2]
    server = sys.argv[3]

    # Parse symbols (comma-separated)
    symbols_str = sys.argv[4] if len(sys.argv) > 4 else 'EURUSD'
    symbols = [s.strip() for s in symbols_str.split(',')]

    # Parse interval
    interval = int(sys.argv[5]) if len(sys.argv) > 5 else 60

    # Create and run monitor
    monitor = BreakoutMonitor(login, password, server, symbols, interval)
    monitor.run()
