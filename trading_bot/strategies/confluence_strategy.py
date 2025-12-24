"""
Main Confluence Strategy
Orchestrates signal detection, position management, and recovery
"""

import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
import time

from core.mt5_manager import MT5Manager
from strategies.signal_detector import SignalDetector
from strategies.recovery_manager import RecoveryManager
from strategies.time_filters import TimeFilter
from strategies.breakout_strategy import BreakoutStrategy
from strategies.partial_close_manager import PartialCloseManager
from utils.risk_calculator import RiskCalculator
from utils.config_reloader import reload_config, print_current_config
from utils.timezone_manager import get_current_time
from portfolio.portfolio_manager import PortfolioManager
from config.strategy_config import (
    SYMBOLS,
    TIMEFRAME,
    HTF_TIMEFRAMES,
    DATA_REFRESH_INTERVAL,
    MAX_OPEN_POSITIONS,
    MAX_POSITIONS_PER_SYMBOL,
    PROFIT_TARGET_PERCENT,
    MAX_POSITION_HOURS,
    PARTIAL_CLOSE_ENABLED,
    PARTIAL_CLOSE_RECOVERY,
    BREAKOUT_ENABLED,
    BREAKOUT_LOT_SIZE_MULTIPLIER,
)


class ConfluenceStrategy:
    """Main trading strategy implementation"""

    def __init__(self, mt5_manager: MT5Manager, test_mode: bool = False):
        """
        Initialize strategy

        Args:
            mt5_manager: MT5Manager instance (already connected)
            test_mode: If True, bypass all time filters for testing
        """
        self.mt5 = mt5_manager
        self.test_mode = test_mode
        self.signal_detector = SignalDetector()
        self.recovery_manager = RecoveryManager()
        self.risk_calculator = RiskCalculator()
        self.portfolio_manager = PortfolioManager()

        # New strategy modules
        self.time_filter = TimeFilter()
        self.breakout_strategy = BreakoutStrategy() if BREAKOUT_ENABLED else None
        self.partial_close_manager = PartialCloseManager() if PARTIAL_CLOSE_ENABLED else None

        self.running = False
        self.last_data_refresh = {}
        self.market_data_cache = {}

        # Statistics
        self.stats = {
            'signals_detected': 0,
            'trades_opened': 0,
            'trades_closed': 0,
            'grid_levels_added': 0,
            'hedges_activated': 0,
            'dca_levels_added': 0,
        }

    def start(self, symbols: List[str]):
        """
        Start the trading strategy

        Args:
            symbols: List of symbols to trade
        """
        print("=" * 80)
        print("🚀 CONFLUENCE STRATEGY STARTING")
        print("=" * 80)
        print()

        # Get account info
        account_info = self.mt5.get_account_info()
        if not account_info:
            print("❌ Failed to get account info")
            return

        print(f"Account Balance: ${account_info['balance']:.2f}")
        print(f"Symbols: {', '.join(symbols)}")
        print(f"Timeframe: {TIMEFRAME}")
        print(f"HTF: {', '.join(HTF_TIMEFRAMES)}")
        print()

        # Set initial balance for drawdown tracking
        self.risk_calculator.set_initial_balance(account_info['balance'])

        self.running = True

        try:
            while self.running:
                # Main trading loop
                self._trading_loop(symbols)

                # Sleep before next iteration
                time.sleep(60)  # Check every minute

        except KeyboardInterrupt:
            print("\n⚠️ Strategy stopped by user")
        except Exception as e:
            print(f"\n❌ Strategy error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop()

    def stop(self):
        """Stop the strategy"""
        self.running = False
        print()
        print("=" * 80)
        print("📊 STRATEGY STATISTICS")
        print("=" * 80)
        for key, value in self.stats.items():
            print(f"{key.replace('_', ' ').title()}: {value}")
        print()

    def _trading_loop(self, symbols: List[str]):
        """
        Main trading loop iteration

        Args:
            symbols: Symbols to trade
        """
        for symbol in symbols:
            try:
                # 1. Check if we should refresh market data
                self._refresh_market_data(symbol)

                # 2. Manage existing positions
                self._manage_positions(symbol)

                # 3. Look for new signals
                if self._can_open_new_position(symbol):
                    self._check_for_signals(symbol)

            except Exception as e:
                print(f"❌ Error processing {symbol}: {e}")
                import traceback
                traceback.print_exc()
                continue

    def _refresh_market_data(self, symbol: str):
        """Refresh market data for symbol if needed"""
        now = get_current_time()
        last_refresh = self.last_data_refresh.get(symbol)

        # Check if refresh needed
        if last_refresh:
            minutes_since = (now - last_refresh).total_seconds() / 60
            if minutes_since < DATA_REFRESH_INTERVAL:
                return  # Data still fresh

        # Fetch H1 data
        h1_data = self.mt5.get_historical_data(symbol, TIMEFRAME, bars=500)
        if h1_data is None:
            return

        # Calculate VWAP on H1 data
        h1_data = self.signal_detector.vwap.calculate(h1_data)

        # Calculate ATR for breakout detection
        if 'atr' not in h1_data.columns:
            # Simple ATR calculation (14 period)
            high_low = h1_data['high'] - h1_data['low']
            high_close = abs(h1_data['high'] - h1_data['close'].shift())
            low_close = abs(h1_data['low'] - h1_data['close'].shift())
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            h1_data['atr'] = true_range.rolling(window=14).mean()

        # Fetch HTF data
        d1_data = self.mt5.get_historical_data(symbol, 'D1', bars=100)
        w1_data = self.mt5.get_historical_data(symbol, 'W1', bars=50)

        if d1_data is None or w1_data is None:
            return

        # Cache the data
        self.market_data_cache[symbol] = {
            'h1': h1_data,
            'd1': d1_data,
            'w1': w1_data,
            'last_update': now
        }

        self.last_data_refresh[symbol] = now

    def _manage_positions(self, symbol: str):
        """Manage existing positions for symbol"""
        positions = self.mt5.get_positions(symbol)

        # Check for trading window closures - close negative positions if window is ending
        close_actions = self.portfolio_manager.check_window_closures()
        for action in close_actions:
            if action.symbol == symbol and action.close_negatives_only:
                # Close all negative positions for this symbol
                for pos in positions:
                    if pos['profit'] < 0:
                        ticket = pos['ticket']
                        print(f"🚪 Closing negative position {ticket} - {action.reason}")
                        if self.mt5.close_position(ticket):
                            self.recovery_manager.untrack_position(ticket)
                            self.stats['trades_closed'] += 1

        for position in positions:
            ticket = position['ticket']
            comment = position.get('comment', '')

            # ⚠️ CRITICAL FIX: Don't track recovery orders as new positions
            # Recovery orders have comments like "Grid L1 - 1001", "Hedge - 1001", "DCA L1 - 1001"
            # Only the ORIGINAL trade should spawn recovery, not recovery orders themselves
            is_recovery_order = any([
                'Grid' in comment,
                'Hedge' in comment,
                'DCA' in comment,
            ])

            # Check if position is being tracked
            if ticket not in self.recovery_manager.tracked_positions:
                # Only track original trades, NOT recovery orders
                if not is_recovery_order:
                    # Start tracking
                    self.recovery_manager.track_position(
                        ticket=ticket,
                        symbol=position['symbol'],
                        entry_price=position['price_open'],
                        position_type=position['type'],
                        volume=position['volume']
                    )
                else:
                    # Skip recovery orders - they're already tracked within their parent position
                    continue

            # Check recovery triggers (only for tracked original positions)
            if ticket in self.recovery_manager.tracked_positions:
                current_price = position['price_current']
                symbol_info = self.mt5.get_symbol_info(symbol)
                pip_value = symbol_info.get('point', 0.0001)

                recovery_actions = self.recovery_manager.check_all_recovery_triggers(
                    ticket, current_price, pip_value
                )

                # Execute recovery actions
                for action in recovery_actions:
                    self._execute_recovery_action(action)

                # Check partial close levels (if enabled and position is in profit)
                # Apply to ALL profitable positions (original + grid entries)
                if self.partial_close_manager and position['profit'] > 0:
                    # Track position if not already tracked
                    if ticket not in self.partial_close_manager.partial_closes:
                        # Calculate TP price based on VWAP or other exit logic
                        # For now, use a reasonable default TP
                        entry_price = position['price_open']
                        pos_type = 'buy' if position['type'] == 0 else 'sell'

                        # Estimate TP price (40 pips for EURUSD, adjust as needed)
                        pip_value = symbol_info.get('point', 0.0001)
                        tp_distance = 40 * pip_value
                        tp_price = entry_price + tp_distance if pos_type == 'buy' else entry_price - tp_distance

                        self.partial_close_manager.track_position(
                            ticket=ticket,
                            entry_price=entry_price,
                            volume=position['volume'],
                            position_type=pos_type,
                            tp_price=tp_price
                        )

                    # Calculate current profit in pips
                    entry_price = position['price_open']
                    current_price = position['price_current']
                    pip_diff = abs(current_price - entry_price) / pip_value

                    # Check for partial close triggers
                    partial_action = self.partial_close_manager.check_partial_close_levels(
                        ticket=ticket,
                        current_price=current_price,
                        current_profit_pips=pip_diff
                    )

                    if partial_action:
                        # Execute partial close
                        close_volume = partial_action['close_volume']
                        print(f"📉 Partial close: {ticket} - {partial_action['close_percent']}% at {partial_action['level_percent']}% to TP")

                        # Check if close_volume equals or exceeds position volume (final close)
                        if close_volume >= position['volume']:
                            # Close entire position instead of partial
                            if self.mt5.close_position(ticket):
                                print(f"✅ Full close successful: {position['volume']} lots (final partial close)")
                                self.recovery_manager.untrack_position(ticket)
                                self.stats['trades_closed'] += 1
                        else:
                            # Close partial volume
                            if self.mt5.close_partial_position(ticket, close_volume):
                                print(f"✅ Partial close successful: {close_volume} lots")

                # Check exit conditions (only for tracked original positions)
                # Priority order: 0) Stack drawdown (risk protection), 1) Profit target, 2) Time limit, 3) VWAP reversion

                # Get account info and positions for checks
                account_info = self.mt5.get_account_info()
                all_positions = self.mt5.get_positions()

                # 0. Check stack drawdown (HIGHEST PRIORITY - risk protection)
                if self.recovery_manager.check_stack_drawdown(
                    ticket=ticket,
                    mt5_positions=all_positions,
                    pip_value=pip_value
                ):
                    self._close_recovery_stack(ticket)
                    continue

                # 1. Check profit target (from config)
                if account_info and self.recovery_manager.check_profit_target(
                    ticket=ticket,
                    mt5_positions=all_positions,
                    account_balance=account_info['balance'],
                    profit_percent=PROFIT_TARGET_PERCENT
                ):
                    self._close_recovery_stack(ticket)
                    continue

                # 2. Check time limit (from config)
                if self.recovery_manager.check_time_limit(ticket, hours_limit=MAX_POSITION_HOURS):
                    self._close_recovery_stack(ticket)
                    continue

            # 3. Check exit signal (VWAP reversion) - only for individual positions
            if symbol in self.market_data_cache:
                h1_data = self.market_data_cache[symbol]['h1']
                should_exit = self.signal_detector.check_exit_signal(position, h1_data)

                if should_exit:
                    print(f"🎯 Exit signal detected for {ticket} - VWAP reversion")
                    if self.mt5.close_position(ticket):
                        self.recovery_manager.untrack_position(ticket)
                        self.stats['trades_closed'] += 1

    def _check_for_signals(self, symbol: str):
        """Check for new entry signals"""
        if symbol not in self.market_data_cache:
            return

        # Check if symbol is tradeable based on portfolio trading windows (bypass in test mode)
        if not self.test_mode and not self.portfolio_manager.is_symbol_tradeable(symbol):
            return  # Not in trading window for this symbol

        cache = self.market_data_cache[symbol]
        h1_data = cache['h1']
        d1_data = cache['d1']
        w1_data = cache['w1']

        current_time = get_current_time()
        signal = None

        # Check which strategy can trade based on time filters (bypass in test mode)
        if self.test_mode:
            can_trade_mr = True
            can_trade_bo = True
        else:
            can_trade_mr = self.time_filter.can_trade_mean_reversion(current_time)
            can_trade_bo = self.time_filter.can_trade_breakout(current_time)

        # Try mean reversion signal first (if allowed)
        if can_trade_mr:
            signal = self.signal_detector.detect_signal(
                current_data=h1_data,
                daily_data=d1_data,
                weekly_data=w1_data,
                symbol=symbol
            )
            if signal:
                signal['strategy_type'] = 'mean_reversion'

        # Try breakout signal (if mean reversion found nothing and breakout is allowed)
        if signal is None and can_trade_bo and self.breakout_strategy:
            # Get current price and volume
            latest_bar = h1_data.iloc[-1]
            current_price = latest_bar['close']

            # Get volume - handle both 'volume' and 'tick_volume' columns
            if 'volume' in latest_bar:
                current_volume = latest_bar['volume']
            elif 'tick_volume' in latest_bar:
                current_volume = latest_bar['tick_volume']
            else:
                current_volume = 0  # Default if no volume data
                print(f"⚠️ Warning: No volume data for {symbol}, using 0")

            # Calculate ATR
            atr = h1_data['atr'].iloc[-1] if 'atr' in h1_data.columns else 0

            # Check for range breakout
            breakout_signal = self.breakout_strategy.detect_range_breakout(
                data=h1_data,
                current_price=current_price,
                current_volume=current_volume,
                atr=atr
            )

            if breakout_signal:
                # Convert breakout signal to standard signal format
                signal = {
                    'symbol': symbol,
                    'direction': breakout_signal['direction'],
                    'price': current_price,
                    'strategy_type': 'breakout',
                    'confluence_score': breakout_signal.get('score', 3),
                    'factors': breakout_signal.get('factors', [])
                }

        if signal is None:
            return

        # Signal detected!
        self.stats['signals_detected'] += 1

        print()
        print(f"🎯 Signal: {signal.get('strategy_type', 'unknown').upper()}")
        print(self.signal_detector.get_signal_summary(signal))
        print()

        # Execute trade
        self._execute_signal(signal)

    def _execute_signal(self, signal: Dict):
        """
        Execute a trading signal

        Args:
            signal: Signal dict from signal detector
        """
        symbol = signal['symbol']
        direction = signal['direction']
        price = signal['price']

        # Get account and symbol info
        account_info = self.mt5.get_account_info()
        symbol_info = self.mt5.get_symbol_info(symbol)

        if not account_info or not symbol_info:
            print("❌ Failed to get account/symbol info")
            return

        # Calculate position size
        volume = self.risk_calculator.calculate_position_size(
            account_balance=account_info['balance'],
            symbol_info=symbol_info
        )

        # Apply breakout multiplier if this is a breakout signal
        if signal.get('strategy_type') == 'breakout':
            volume = volume * BREAKOUT_LOT_SIZE_MULTIPLIER
            # Round to broker's volume step
            volume_step = symbol_info.get('volume_step', 0.01)
            volume = round(volume / volume_step) * volume_step
            # Ensure minimum volume
            volume = max(symbol_info.get('volume_min', 0.01), volume)
            print(f"📉 Breakout signal: Reducing lot size to {volume} (50% of base)")

        # Get current positions for validation
        positions = self.mt5.get_positions()

        # Validate trade
        can_trade, reason = self.risk_calculator.validate_trade(
            account_info=account_info,
            symbol_info=symbol_info,
            volume=volume,
            current_positions=positions
        )

        if not can_trade:
            print(f"❌ Trade validation failed: {reason}")
            return

        # Place order
        comment = f"Confluence:{signal['confluence_score']}"

        ticket = self.mt5.place_order(
            symbol=symbol,
            order_type=direction,
            volume=volume,
            sl=None,  # EA doesn't use hard stops
            tp=None,  # Using VWAP reversion instead
            comment=comment
        )

        if ticket:
            self.stats['trades_opened'] += 1
            print(f"✅ Trade opened: Ticket {ticket}")

            # Start tracking for recovery
            self.recovery_manager.track_position(
                ticket=ticket,
                symbol=symbol,
                entry_price=price,
                position_type=direction,
                volume=volume
            )

    def _close_recovery_stack(self, original_ticket: int):
        """
        Close entire recovery stack (original + grid + hedge + DCA)

        Args:
            original_ticket: Original position ticket
        """
        # Get all tickets in the stack
        stack_tickets = self.recovery_manager.get_all_stack_tickets(original_ticket)

        print(f"📦 Closing recovery stack for {original_ticket}")
        print(f"   Closing {len(stack_tickets)} positions...")

        closed_count = 0
        for ticket in stack_tickets:
            if self.mt5.close_position(ticket):
                closed_count += 1
                self.stats['trades_closed'] += 1
                print(f"   ✅ Closed #{ticket}")
            else:
                print(f"   ❌ Failed to close #{ticket}")

        # Untrack the original position
        self.recovery_manager.untrack_position(original_ticket)

        print(f"📦 Stack closed: {closed_count}/{len(stack_tickets)} positions")

    def _execute_recovery_action(self, action: Dict):
        """
        Execute a recovery action (grid/hedge/dca)

        Args:
            action: Recovery action dict
        """
        action_type = action['action']
        symbol = action['symbol']
        order_type = action['type']
        volume = action['volume']
        comment = action['comment']
        original_ticket = action.get('original_ticket')

        # Place order
        ticket = self.mt5.place_order(
            symbol=symbol,
            order_type=order_type,
            volume=volume,
            comment=comment
        )

        if ticket:
            # Store the recovery ticket in the manager
            if original_ticket:
                self.recovery_manager.store_recovery_ticket(
                    original_ticket=original_ticket,
                    recovery_ticket=ticket,
                    action_type=action_type
                )

            # Update statistics
            if action_type == 'grid':
                self.stats['grid_levels_added'] += 1
            elif action_type == 'hedge':
                self.stats['hedges_activated'] += 1
            elif action_type == 'dca':
                self.stats['dca_levels_added'] += 1

    def _can_open_new_position(self, symbol: str) -> bool:
        """Check if we can open a new position"""
        # Check total positions
        all_positions = self.mt5.get_positions()
        if len(all_positions) >= MAX_OPEN_POSITIONS:
            return False

        # Check positions per symbol
        symbol_positions = self.mt5.get_positions(symbol)
        if len(symbol_positions) >= MAX_POSITIONS_PER_SYMBOL:
            return False

        return True

    def get_status(self) -> Dict:
        """Get current strategy status"""
        account_info = self.mt5.get_account_info()
        positions = self.mt5.get_positions()

        risk_metrics = self.risk_calculator.get_risk_metrics(
            account_info=account_info or {},
            positions=positions
        )

        recovery_status = self.recovery_manager.get_all_positions_status()

        return {
            'running': self.running,
            'account': account_info,
            'risk_metrics': risk_metrics,
            'positions': positions,
            'recovery_status': recovery_status,
            'statistics': self.stats,
            'cached_symbols': list(self.market_data_cache.keys()),
        }

    def reload_config(self):
        """
        Reload configuration from strategy_config.py without restarting bot
        Fixes Python caching issue where config changes require full restart
        """
        print()
        print("=" * 60)
        print("🔄 RELOADING CONFIGURATION")
        print("=" * 60)
        success = reload_config()
        if success:
            print_current_config()
            print("✅ Config reloaded successfully!")
            print("   Changes will take effect on next trading cycle")
        else:
            print("❌ Config reload failed")
        print("=" * 60)
        print()
        return success
