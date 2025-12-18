"""
Scalping Strategy
Fast momentum-based scalping on M1/M5 timeframes
No recovery mechanisms - straight in/out with tight stops
"""

import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, time
import time as time_module

from core.mt5_manager import MT5Manager
from strategies.scalping_signal_detector import ScalpingSignalDetector
from utils.risk_calculator import RiskCalculator
from utils.logger import logger


class ScalpingStrategy:
    """
    Momentum-based scalping strategy

    Features:
    - Fast M1/M5 entries based on RSI, Stochastic, Volume, Breakouts
    - Tight 5-8 pip stops with 2:1 R:R targets
    - No recovery mechanisms (no grid/hedge/DCA)
    - Session-based trading (high volatility periods only)
    - Maximum 3-5 minute hold time target
    """

    def __init__(self, mt5_manager: MT5Manager, config: Dict):
        """
        Initialize scalping strategy

        Args:
            mt5_manager: MT5Manager instance
            config: Scalping configuration dict
        """
        self.mt5 = mt5_manager
        self.config = config

        # Initialize components
        self.signal_detector = ScalpingSignalDetector(
            momentum_period=config.get('SCALP_MOMENTUM_PERIOD', 14),
            volume_spike_threshold=config.get('SCALP_VOLUME_SPIKE_THRESHOLD', 1.5),
            breakout_lookback=config.get('SCALP_BREAKOUT_LOOKBACK', 20)
        )
        self.risk_calculator = RiskCalculator()

        self.running = False
        self.active_scalps = {}  # Track active scalping positions

        # Statistics
        self.stats = {
            'signals_detected': 0,
            'trades_opened': 0,
            'trades_closed': 0,
            'wins': 0,
            'losses': 0,
            'total_pips': 0,
        }

    def start(self, symbols: List[str]):
        """
        Start the scalping strategy

        Args:
            symbols: List of symbols to scalp
        """
        print("=" * 80)
        print("⚡ SCALPING STRATEGY STARTING")
        print("=" * 80)
        print(f"Timeframe: {self.config.get('SCALP_TIMEFRAME', 'M1')}")
        print(f"Symbols: {', '.join(symbols)}")
        print(f"Max Positions: {self.config.get('SCALP_MAX_POSITIONS', 3)}")
        print(f"Lot Size: {self.config.get('SCALP_LOT_SIZE', 0.01)}")
        print()

        # Get account info
        account_info = self.mt5.get_account_info()
        if not account_info:
            print("❌ Failed to get account info")
            return

        print(f"Account Balance: ${account_info['balance']:.2f}")
        print(f"Account Equity: ${account_info['equity']:.2f}")
        print()

        self.running = True

        try:
            while self.running:
                # Main scalping loop
                self._scalping_loop(symbols)

                # Check faster than confluence strategy (every 10 seconds for M1)
                sleep_seconds = self.config.get('SCALP_CHECK_INTERVAL_SECONDS', 10)
                time_module.sleep(sleep_seconds)

        except KeyboardInterrupt:
            print("\n⚠️ Scalping strategy stopped by user")
        except Exception as e:
            print(f"\n❌ Scalping strategy error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop()

    def stop(self):
        """Stop the strategy"""
        self.running = False
        print()
        print("=" * 80)
        print("📊 SCALPING STATISTICS")
        print("=" * 80)
        for key, value in self.stats.items():
            print(f"{key.replace('_', ' ').title()}: {value}")

        # Calculate win rate
        total_closed = self.stats['wins'] + self.stats['losses']
        if total_closed > 0:
            win_rate = (self.stats['wins'] / total_closed) * 100
            print(f"Win Rate: {win_rate:.1f}%")
            print(f"Average Pips: {self.stats['total_pips'] / total_closed:.1f}")
        print()

    def _scalping_loop(self, symbols: List[str]):
        """
        Main scalping loop iteration

        Args:
            symbols: Symbols to scalp
        """
        # 1. Check if we're in allowed trading session
        if not self._is_trading_session():
            return

        for symbol in symbols:
            try:
                # 2. Manage existing positions first
                self._manage_scalping_positions(symbol)

                # 3. Look for new signals if we have capacity
                if self._can_open_scalp(symbol):
                    self._check_for_scalp_signal(symbol)

            except Exception as e:
                logger.error(f"Error in scalping loop for {symbol}: {e}")
                continue

    def _is_trading_session(self) -> bool:
        """
        Check if current time is within allowed trading sessions

        Scalping works best during high volatility:
        - London open: 08:00-12:00 UTC
        - NY open: 13:00-17:00 UTC
        - London/NY overlap: 13:00-16:00 UTC (best)
        """
        enabled_sessions = self.config.get('SCALP_TRADING_SESSIONS', {})

        if not enabled_sessions:
            return True  # No filter = always trade

        current_time = datetime.now().time()

        for session_name, session_config in enabled_sessions.items():
            if not session_config.get('enabled', False):
                continue

            start_str = session_config.get('start', '00:00')
            end_str = session_config.get('end', '23:59')

            start_time = time(*map(int, start_str.split(':')))
            end_time = time(*map(int, end_str.split(':')))

            # Handle sessions that cross midnight
            if start_time <= end_time:
                if start_time <= current_time <= end_time:
                    return True
            else:
                if current_time >= start_time or current_time <= end_time:
                    return True

        return False

    def _check_for_scalp_signal(self, symbol: str):
        """Check for scalping signal on symbol"""
        # Get M1/M5 data
        timeframe = self.config.get('SCALP_TIMEFRAME', 'M1')
        bars = self.config.get('SCALP_BARS_TO_FETCH', 100)

        data = self.mt5.get_historical_data(symbol, timeframe, bars=bars)

        if data is None or len(data) < 50:
            return

        # Detect signal
        signal = self.signal_detector.detect_signal(data, symbol)

        if signal is None:
            return

        # Signal detected!
        self.stats['signals_detected'] += 1

        print()
        print(self.signal_detector.get_signal_summary(signal))
        print()

        # Execute trade
        self._execute_scalp(signal)

    def _execute_scalp(self, signal: Dict):
        """
        Execute scalping trade

        Args:
            signal: Signal dict from scalping detector
        """
        symbol = signal['symbol']
        direction = signal['direction']
        stop_loss = signal['stop_loss']
        take_profit = signal['take_profit']

        # Get account and symbol info
        account_info = self.mt5.get_account_info()
        symbol_info = self.mt5.get_symbol_info(symbol)

        if not account_info or not symbol_info:
            print("❌ Failed to get account/symbol info")
            return

        # Use fixed lot size for scalping (configurable)
        volume = self.config.get('SCALP_LOT_SIZE', 0.01)

        # Place order with tight SL and TP
        comment = f"Scalp:{signal['strength']}"

        ticket = self.mt5.place_order(
            symbol=symbol,
            order_type=direction,
            volume=volume,
            sl=stop_loss,
            tp=take_profit,
            comment=comment
        )

        if ticket:
            self.stats['trades_opened'] += 1
            print(f"✅ Scalp opened: Ticket #{ticket}")
            print(f"   Direction: {direction.upper()}")
            print(f"   SL: {stop_loss:.5f} | TP: {take_profit:.5f}")

            # Track this scalp
            self.active_scalps[ticket] = {
                'symbol': symbol,
                'entry_time': datetime.now(),
                'entry_price': signal['price'],
                'direction': direction,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'volume': volume
            }

    def _manage_scalping_positions(self, symbol: str):
        """
        Manage existing scalping positions

        Scalping exits:
        1. Hit TP (auto-closed by broker)
        2. Hit SL (auto-closed by broker)
        3. Manual time-based exit (if held too long)
        4. Trailing stop (optional)
        """
        positions = self.mt5.get_positions(symbol)

        for position in positions:
            ticket = position['ticket']
            comment = position.get('comment', '')

            # Only manage scalping positions
            if 'Scalp' not in comment:
                continue

            # Check if this position hit TP/SL (closed by broker)
            if ticket in self.active_scalps:
                # Position still open - check time limit
                scalp_info = self.active_scalps[ticket]
                entry_time = scalp_info['entry_time']

                # Calculate hold time
                hold_minutes = (datetime.now() - entry_time).total_seconds() / 60
                max_hold_minutes = self.config.get('SCALP_MAX_HOLD_MINUTES', 10)

                if hold_minutes > max_hold_minutes:
                    print(f"⏱️ Scalp #{ticket} held too long ({hold_minutes:.1f}min) - closing")
                    if self.mt5.close_position(ticket):
                        self._record_scalp_exit(ticket, position, 'time_exit')

                # Optional: Implement trailing stop
                elif self.config.get('SCALP_USE_TRAILING_STOP', False):
                    self._update_trailing_stop(ticket, position, scalp_info)

        # Clean up closed positions from tracking
        self._cleanup_closed_scalps()

    def _update_trailing_stop(self, ticket: int, position: Dict, scalp_info: Dict):
        """
        Update trailing stop for profitable scalp

        Args:
            ticket: Position ticket
            position: Current position data from MT5
            scalp_info: Tracked scalp info
        """
        current_price = position['price_current']
        entry_price = scalp_info['entry_price']
        direction = scalp_info['direction']

        trailing_pips = self.config.get('SCALP_TRAILING_STOP_PIPS', 5)
        trailing_distance = trailing_pips * 0.0001  # Convert pips to price

        current_sl = position.get('sl', 0)

        # Calculate profit in pips
        if direction == 'buy':
            profit_pips = (current_price - entry_price) * 10000

            # Move stop to breakeven once in profit
            if profit_pips >= trailing_pips and current_sl < entry_price:
                new_sl = entry_price
                print(f"📍 Moving SL to breakeven for scalp #{ticket}")
                self.mt5.modify_position(ticket, sl=new_sl)

            # Trail stop if deeper in profit
            elif profit_pips >= trailing_pips * 2:
                new_sl = current_price - trailing_distance
                if new_sl > current_sl:
                    print(f"📍 Trailing SL for scalp #{ticket}: {new_sl:.5f}")
                    self.mt5.modify_position(ticket, sl=new_sl)

        else:  # sell
            profit_pips = (entry_price - current_price) * 10000

            # Move stop to breakeven once in profit
            if profit_pips >= trailing_pips and (current_sl == 0 or current_sl > entry_price):
                new_sl = entry_price
                print(f"📍 Moving SL to breakeven for scalp #{ticket}")
                self.mt5.modify_position(ticket, sl=new_sl)

            # Trail stop if deeper in profit
            elif profit_pips >= trailing_pips * 2:
                new_sl = current_price + trailing_distance
                if current_sl == 0 or new_sl < current_sl:
                    print(f"📍 Trailing SL for scalp #{ticket}: {new_sl:.5f}")
                    self.mt5.modify_position(ticket, sl=new_sl)

    def _cleanup_closed_scalps(self):
        """Remove closed positions from active tracking"""
        all_positions = self.mt5.get_positions()
        open_tickets = {pos['ticket'] for pos in all_positions}

        closed_tickets = []
        for ticket in self.active_scalps.keys():
            if ticket not in open_tickets:
                closed_tickets.append(ticket)

        for ticket in closed_tickets:
            # Try to get closed position info from history
            # (This would require MT5 history lookup - simplified here)
            self._record_scalp_exit(ticket, None, 'tp_or_sl')
            del self.active_scalps[ticket]

    def _record_scalp_exit(self, ticket: int, position: Optional[Dict], exit_reason: str):
        """Record scalp exit statistics"""
        if ticket not in self.active_scalps:
            return

        scalp_info = self.active_scalps[ticket]

        if position:
            current_price = position['price_current']
            profit = position.get('profit', 0)
        else:
            # Position already closed - can't get current stats
            current_price = None
            profit = 0

        # Calculate profit in pips
        if current_price:
            entry_price = scalp_info['entry_price']
            direction = scalp_info['direction']

            if direction == 'buy':
                pips = (current_price - entry_price) * 10000
            else:
                pips = (entry_price - current_price) * 10000

            self.stats['total_pips'] += pips

            if profit > 0 or pips > 0:
                self.stats['wins'] += 1
                print(f"✅ Scalp #{ticket} closed: +{pips:.1f} pips ({exit_reason})")
            else:
                self.stats['losses'] += 1
                print(f"❌ Scalp #{ticket} closed: {pips:.1f} pips ({exit_reason})")

        self.stats['trades_closed'] += 1

    def _can_open_scalp(self, symbol: str) -> bool:
        """Check if we can open a new scalp position"""
        # Check max scalping positions
        max_scalps = self.config.get('SCALP_MAX_POSITIONS', 3)
        current_scalps = len(self.active_scalps)

        if current_scalps >= max_scalps:
            return False

        # Check max scalps per symbol
        max_per_symbol = self.config.get('SCALP_MAX_POSITIONS_PER_SYMBOL', 1)
        symbol_scalps = sum(1 for info in self.active_scalps.values()
                           if info['symbol'] == symbol)

        if symbol_scalps >= max_per_symbol:
            return False

        return True

    def get_status(self) -> Dict:
        """Get current scalping strategy status"""
        return {
            'running': self.running,
            'active_scalps': len(self.active_scalps),
            'statistics': self.stats,
            'config': self.config,
        }
