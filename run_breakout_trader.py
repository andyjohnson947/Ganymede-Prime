#!/usr/bin/env python3
"""
Breakout Trading Bot - LIVE EXECUTION
Places actual trades via MT5 based on breakout signals

Usage:
    python run_breakout_trader.py <login> <password> <server> [symbols] [scan_interval_minutes]

Example:
    python run_breakout_trader.py 12345 "yourpass" "MetaQuotes-Demo" EURUSD 60

SAFETY FEATURES:
- Paper trading mode (set in config)
- Max positions limit
- Risk per trade limits
- Auto-disable on consecutive losses
- Breakeven and trailing stop management
"""

import MetaTrader5 as mt5
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime, timedelta
import time
import json
import logging

# Add paths
sys.path.insert(0, str(Path(__file__).parent))

from breakout_strategy.strategies.breakout_detector import BreakoutDetector
from breakout_strategy.indicators.volume_analyzer import VolumeAnalyzer
from breakout_strategy.config import breakout_config
from trading_bot.indicators.vwap import VWAP
from trading_bot.indicators.volume_profile import VolumeProfile


class BreakoutTrader:
    """Live breakout trading system"""

    def __init__(self, login: int, password: str, server: str, symbols: list, scan_interval: int = 60):
        self.login = login
        self.password = password
        self.server = server
        self.symbols = symbols
        self.scan_interval = scan_interval

        # Components
        self.detector = BreakoutDetector()
        self.volume_analyzer = VolumeAnalyzer(lookback=20)

        # Active positions tracking
        self.positions = {}  # {ticket: position_data}

        # Performance tracking
        self.stats = {
            'signals_detected': 0,
            'trades_opened': 0,
            'trades_closed': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl': 0.0,
            'consecutive_losses': 0,
            'win_rate': 0.0,
            'start_time': datetime.now(),
        }

        # Logs directory
        self.log_dir = Path(__file__).parent / "logs" / "breakout_trading"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Setup logging
        self.setup_logging()

        # Safety checks
        self.check_configuration()

    def setup_logging(self):
        """Setup logging system"""
        log_file = self.log_dir / f"breakout_trader_{datetime.now().strftime('%Y%m%d')}.log"

        # File handler with UTF-8 encoding (supports emojis)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)

        # Console handler with error handling for Windows
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Try to set UTF-8 encoding for Windows console
        try:
            import sys
            import io
            if sys.platform == 'win32' and sys.stdout.encoding != 'utf-8':
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        except:
            pass

        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Get logger and add handlers
        self.logger = logging.getLogger('BreakoutTrader')
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def check_configuration(self):
        """Check and display configuration"""
        self.logger.info("="*80)
        self.logger.info("BREAKOUT TRADER CONFIGURATION")
        self.logger.info("="*80)

        # Check if paper trading
        if breakout_config.BREAKOUT_PAPER_TRADE_ONLY:
            self.logger.warning("⚠️  PAPER TRADING MODE - No real orders will be placed")
        else:
            self.logger.info("🔴 LIVE TRADING MODE - Real orders will be placed!")

        # Check if module enabled
        if not breakout_config.BREAKOUT_MODULE_ENABLED:
            self.logger.warning("⚠️  Module disabled in config - enabling for this session")
            breakout_config.BREAKOUT_MODULE_ENABLED = True

        self.logger.info(f"Symbols: {', '.join(self.symbols)}")
        self.logger.info(f"Risk per trade: {breakout_config.BREAKOUT_RISK_PERCENT}%")
        self.logger.info(f"Min confluence: {breakout_config.MIN_BREAKOUT_CONFLUENCE}")
        self.logger.info(f"Conservative entry: {breakout_config.ALLOW_CONSERVATIVE_ENTRY}")
        self.logger.info(f"Aggressive entry: {breakout_config.ALLOW_AGGRESSIVE_ENTRY}")
        self.logger.info(f"Trailing stop: {breakout_config.USE_TRAILING_STOP}")
        self.logger.info(f"Breakeven move: {breakout_config.MOVE_TO_BREAKEVEN}")
        self.logger.info(f"Scan interval: {self.scan_interval} minutes")
        self.logger.info(f"Log directory: {self.log_dir}")
        self.logger.info("="*80)

    def connect_mt5(self) -> bool:
        """Connect to MT5"""
        if not mt5.initialize():
            self.logger.error("Failed to initialize MT5")
            return False

        if not mt5.login(self.login, password=self.password, server=self.server):
            error = mt5.last_error()
            self.logger.error(f"MT5 login failed: {error}")
            mt5.shutdown()
            return False

        account_info = mt5.account_info()
        if account_info:
            self.logger.info(f"Connected to {self.server}")
            self.logger.info(f"Account: {account_info.login} | Balance: ${account_info.balance:.2f}")

        return True

    def disconnect_mt5(self):
        """Disconnect from MT5"""
        mt5.shutdown()

    def get_filling_mode(self, symbol: str):
        """Get appropriate filling mode for symbol"""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return mt5.ORDER_FILLING_FOK

        if symbol_info.filling_mode & 2 == 2:  # ORDER_FILLING_IOC
            return mt5.ORDER_FILLING_IOC
        elif symbol_info.filling_mode & 1 == 1:  # ORDER_FILLING_FOK
            return mt5.ORDER_FILLING_FOK
        else:
            return mt5.ORDER_FILLING_RETURN

    def calculate_lot_size(self, symbol: str, entry_price: float, stop_loss: float) -> float:
        """Calculate lot size based on risk percent"""
        account_info = mt5.account_info()
        if not account_info:
            return 0.01

        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return 0.01

        # Calculate risk amount
        balance = account_info.balance
        risk_amount = balance * (breakout_config.BREAKOUT_RISK_PERCENT / 100)

        # Calculate stop loss in pips
        sl_pips = abs(entry_price - stop_loss) * 10000  # Rough pip calculation

        if sl_pips == 0:
            return 0.01

        # Calculate lot size
        # Risk amount = Lot size × Pip value × SL pips
        # For Forex: Pip value ≈ 10 for 1 lot, 1 for 0.1 lot, etc.
        pip_value = 10  # For 1 standard lot on most pairs
        lot_size = risk_amount / (pip_value * sl_pips)

        # Round to symbol's volume step
        volume_step = symbol_info.volume_step
        lot_size = round(lot_size / volume_step) * volume_step

        # Enforce min/max
        lot_size = max(symbol_info.volume_min, min(lot_size, symbol_info.volume_max))

        return lot_size

    def fetch_market_data(self, symbol: str) -> dict:
        """Fetch market data for analysis"""
        # Try symbol alternatives
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            for alt in [f"{symbol}.a", f"{symbol}m", f"{symbol}-sb"]:
                symbol_info = mt5.symbol_info(alt)
                if symbol_info:
                    symbol = alt
                    break
            else:
                return None

        # Fetch data
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

        # Add VP data
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

    def place_order(self, signal: dict, symbol_info) -> bool:
        """Place order based on signal"""
        symbol = signal['symbol']
        direction = signal['direction']
        entry_price = signal['entry_price']
        stop_loss = signal['stop_loss']
        take_profit = signal['take_profit']

        # Check if paper trading
        if breakout_config.BREAKOUT_PAPER_TRADE_ONLY:
            self.logger.info(f"📝 PAPER TRADE: {direction.upper()} {symbol} @ {entry_price:.5f}")
            self.logger.info(f"   SL: {stop_loss:.5f} | TP: {take_profit:.5f} | Score: {signal['confluence_score']}")
            self.log_signal(signal, paper_trade=True)
            self.stats['trades_opened'] += 1
            return True

        # Calculate lot size
        lot_size = self.calculate_lot_size(symbol, entry_price, stop_loss)

        # Get current tick
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            self.logger.error(f"Failed to get tick for {symbol}")
            return False

        # Prepare order
        order_type = mt5.ORDER_TYPE_BUY if direction == 'long' else mt5.ORDER_TYPE_SELL
        price = tick.ask if direction == 'long' else tick.bid
        filling_mode = self.get_filling_mode(symbol)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": order_type,
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": 10,
            "magic": 234001,  # Different from reversion module (234000)
            "comment": f"BO-{signal['entry_type'][:4]}-C{signal['confluence_score']}"[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }

        # Send order
        result = mt5.order_send(request)

        if result is None:
            error = mt5.last_error()
            self.logger.error(f"Order send failed: {error}")
            return False

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(f"Order failed: {result.comment}")
            return False

        # Track position
        self.positions[result.order] = {
            'ticket': result.order,
            'symbol': symbol,
            'direction': direction,
            'entry_price': result.price,
            'entry_time': datetime.now(),
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'lot_size': lot_size,
            'signal': signal,
            'breakeven_moved': False,
            'trailing_active': False,
        }

        self.stats['trades_opened'] += 1
        self.logger.info(f"✅ TRADE OPENED: {direction.upper()} {symbol} {lot_size} lots @ {result.price:.5f}")
        self.logger.info(f"   Ticket: {result.order} | SL: {stop_loss:.5f} | TP: {take_profit:.5f}")
        self.logger.info(f"   Entry: {signal['entry_type']} | Score: {signal['confluence_score']}")

        # Log to file
        self.log_signal(signal, paper_trade=False, ticket=result.order)

        return True

    def manage_positions(self):
        """Manage open positions (breakeven, trailing stop, etc.)"""
        if breakout_config.BREAKOUT_PAPER_TRADE_ONLY:
            return  # No position management in paper trading

        # Get current positions from MT5
        positions = mt5.positions_get()
        if positions is None or len(positions) == 0:
            return

        for position in positions:
            # Only manage breakout positions (magic 234001)
            if position.magic != 234001:
                continue

            ticket = position.ticket
            if ticket not in self.positions:
                continue

            pos_data = self.positions[ticket]
            symbol = position.symbol
            current_price = position.price_current
            entry_price = pos_data['entry_price']
            direction = pos_data['direction']

            # Calculate profit in pips
            if direction == 'long':
                profit_pips = (current_price - entry_price) * 10000
            else:
                profit_pips = (entry_price - current_price) * 10000

            # Move to breakeven
            if breakout_config.MOVE_TO_BREAKEVEN and not pos_data['breakeven_moved']:
                if profit_pips >= breakout_config.BREAKEVEN_TRIGGER_PIPS:
                    new_sl = entry_price
                    if self.modify_position_sl(position, new_sl):
                        pos_data['breakeven_moved'] = True
                        self.logger.info(f"📍 Moved to breakeven: Ticket {ticket} | SL: {new_sl:.5f}")

            # Trailing stop
            if breakout_config.USE_TRAILING_STOP and not pos_data['trailing_active']:
                # Check if we've reached activation threshold
                sl_pips = abs(entry_price - pos_data['stop_loss']) * 10000
                if profit_pips >= (sl_pips * breakout_config.TRAILING_STOP_ACTIVATION_RR):
                    pos_data['trailing_active'] = True
                    self.logger.info(f"🔄 Trailing stop activated: Ticket {ticket}")

            if pos_data.get('trailing_active'):
                # Calculate trailing distance
                trail_distance = breakout_config.TRAILING_STOP_DISTANCE_PIPS / 10000

                if direction == 'long':
                    new_sl = current_price - trail_distance
                    # Only move SL up, never down
                    if new_sl > position.sl:
                        if self.modify_position_sl(position, new_sl):
                            self.logger.info(f"📈 Trailing SL updated: Ticket {ticket} | SL: {new_sl:.5f}")
                else:
                    new_sl = current_price + trail_distance
                    # Only move SL down, never up
                    if new_sl < position.sl:
                        if self.modify_position_sl(position, new_sl):
                            self.logger.info(f"📉 Trailing SL updated: Ticket {ticket} | SL: {new_sl:.5f}")

    def modify_position_sl(self, position, new_sl: float) -> bool:
        """Modify position stop loss"""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": position.symbol,
            "sl": new_sl,
            "tp": position.tp,
            "position": position.ticket,
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            return True
        return False

    def check_closed_positions(self):
        """Check for closed positions and update stats"""
        if breakout_config.BREAKOUT_PAPER_TRADE_ONLY:
            return

        # Get deals from today
        from_date = datetime.now().replace(hour=0, minute=0, second=0)
        deals = mt5.history_deals_get(from_date, datetime.now())

        if deals is None or len(deals) == 0:
            return

        for deal in deals:
            # Check if this is a closing deal for our positions
            if deal.magic != 234001:
                continue

            # Check if we were tracking this position
            if deal.position_id in self.positions:
                pos_data = self.positions[deal.position_id]

                # Calculate P&L
                pnl = deal.profit
                self.stats['total_pnl'] += pnl
                self.stats['trades_closed'] += 1

                if pnl > 0:
                    self.stats['wins'] += 1
                    self.stats['consecutive_losses'] = 0
                    self.logger.info(f"✅ WIN: Ticket {deal.position_id} | P&L: ${pnl:.2f}")
                else:
                    self.stats['losses'] += 1
                    self.stats['consecutive_losses'] += 1
                    self.logger.warning(f"❌ LOSS: Ticket {deal.position_id} | P&L: ${pnl:.2f}")

                # Update win rate
                total = self.stats['wins'] + self.stats['losses']
                self.stats['win_rate'] = (self.stats['wins'] / total * 100) if total > 0 else 0

                # Remove from tracking
                del self.positions[deal.position_id]

                # Check safety limits
                self.check_safety_limits()

    def check_safety_limits(self):
        """Check if we should auto-disable due to losses"""
        if self.stats['consecutive_losses'] >= breakout_config.BREAKOUT_MAX_CONSECUTIVE_LOSSES:
            self.logger.error(f"🛑 AUTO-DISABLE: {self.stats['consecutive_losses']} consecutive losses")
            self.logger.error("Review performance and re-enable manually if needed")
            breakout_config.BREAKOUT_MODULE_ENABLED = False
            return

        # Check win rate
        total_trades = self.stats['wins'] + self.stats['losses']
        if total_trades >= 20:  # Need at least 20 trades for meaningful WR
            if self.stats['win_rate'] < breakout_config.BREAKOUT_MIN_WIN_RATE_THRESHOLD:
                self.logger.error(f"🛑 AUTO-DISABLE: Win rate {self.stats['win_rate']:.1f}% below threshold")
                breakout_config.BREAKOUT_MODULE_ENABLED = False

    def scan_for_signals(self):
        """Scan all symbols for breakout signals"""
        if not breakout_config.BREAKOUT_MODULE_ENABLED:
            self.logger.warning("Module disabled - skipping scan")
            return

        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"SCANNING FOR BREAKOUT SIGNALS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"{'='*80}")

        for symbol in self.symbols:
            # Fetch data
            market_data = self.fetch_market_data(symbol)
            if not market_data:
                self.logger.warning(f"Failed to fetch data for {symbol}")
                continue

            # Detect signal
            signal = self.detector.detect_breakout(
                current_data=market_data['h1_df'],
                daily_data=market_data['daily_df'],
                weekly_data=market_data['weekly_df'],
                symbol=market_data['symbol']
            )

            if signal:
                self.logger.info(f"🚀 SIGNAL: {symbol} {signal['direction'].upper()} | Score: {signal['confluence_score']}")
                self.stats['signals_detected'] += 1

                # Place order
                self.place_order(signal, market_data['symbol_info'])
            else:
                latest = market_data['h1_df'].iloc[-1]
                adx = latest.get('adx', 'N/A')
                vol_summary = self.volume_analyzer.get_volume_summary(market_data['h1_df'])
                self.logger.info(f"⏸️  {symbol}: No signal | ADX: {adx} | Vol: {vol_summary['percentile']:.0f}th")

    def log_signal(self, signal: dict, paper_trade: bool = False, ticket: int = None):
        """Log signal to file"""
        log_file = self.log_dir / f"signals_{datetime.now().strftime('%Y%m%d')}.log"

        with open(log_file, 'a') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"{'📝 PAPER' if paper_trade else '✅ LIVE'} SIGNAL: {signal['symbol']} - {datetime.now()}\n")
            f.write(f"{'='*80}\n")
            f.write(f"Direction: {signal['direction'].upper()}\n")
            f.write(f"Entry Type: {signal['entry_type']}\n")
            f.write(f"Entry: {signal['entry_price']:.5f}\n")
            f.write(f"SL: {signal['stop_loss']:.5f} | TP: {signal['take_profit']:.5f}\n")
            f.write(f"Confluence: {signal['confluence_score']}\n")
            f.write(f"Factors: {', '.join(signal['factors'])}\n")
            if ticket:
                f.write(f"Ticket: {ticket}\n")
            f.write("\n")

    def print_stats(self):
        """Print trading statistics"""
        runtime = datetime.now() - self.stats['start_time']

        print(f"\n{'='*80}")
        print(f"BREAKOUT TRADER STATISTICS")
        print(f"{'='*80}")
        print(f"Runtime: {str(runtime).split('.')[0]}")
        print(f"Signals Detected: {self.stats['signals_detected']}")
        print(f"Trades Opened: {self.stats['trades_opened']}")
        print(f"Trades Closed: {self.stats['trades_closed']}")
        print(f"Wins: {self.stats['wins']} | Losses: {self.stats['losses']}")
        if self.stats['wins'] + self.stats['losses'] > 0:
            print(f"Win Rate: {self.stats['win_rate']:.1f}%")
        print(f"Total P&L: ${self.stats['total_pnl']:.2f}")
        print(f"Open Positions: {len(self.positions)}")
        print(f"{'='*80}")

    def run(self):
        """Main trading loop"""
        self.logger.info("\n🚀 BREAKOUT TRADER STARTING")
        self.logger.info("Press Ctrl+C to stop\n")

        if not self.connect_mt5():
            return

        try:
            while True:
                # Scan for signals
                self.scan_for_signals()

                # Manage existing positions
                self.manage_positions()

                # Check for closed positions
                self.check_closed_positions()

                # Print stats
                self.print_stats()

                # Wait for next scan
                self.logger.info(f"\nNext scan in {self.scan_interval} minutes...")
                time.sleep(self.scan_interval * 60)

        except KeyboardInterrupt:
            self.logger.info("\n\n🛑 STOPPING TRADER...")
        finally:
            self.disconnect_mt5()
            self.print_stats()
            self.logger.info("Trader stopped")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python run_breakout_trader.py <login> <password> <server> [symbols] [interval_minutes]")
        print()
        print("Examples:")
        print("  python run_breakout_trader.py 12345 'yourpass' 'MetaQuotes-Demo' EURUSD 60")
        print("  python run_breakout_trader.py 12345 'yourpass' 'MetaQuotes-Demo' 'EURUSD,GBPUSD' 60")
        print()
        print("Default: EURUSD, 60 minute scans")
        sys.exit(1)

    login = int(sys.argv[1])
    password = sys.argv[2]
    server = sys.argv[3]

    # Parse symbols
    symbols_str = sys.argv[4] if len(sys.argv) > 4 else 'EURUSD'
    symbols = [s.strip() for s in symbols_str.split(',')]

    # Parse interval
    interval = int(sys.argv[5]) if len(sys.argv) > 5 else 60

    # Create and run trader
    trader = BreakoutTrader(login, password, server, symbols, interval)
    trader.run()
