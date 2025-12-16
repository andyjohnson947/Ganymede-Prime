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
from utils.risk_calculator import RiskCalculator
from utils.config_reloader import reload_config, print_current_config
from utils.position_reporter import PositionStatusReporter
from config.strategy_config import (
    SYMBOLS,
    TIMEFRAME,
    HTF_TIMEFRAMES,
    DATA_REFRESH_INTERVAL,
    MAX_OPEN_POSITIONS,
    MAX_POSITIONS_PER_SYMBOL,
    PROFIT_TARGET_PERCENT,
    MAX_POSITION_HOURS,
    STATUS_REPORT_ENABLED,
    STATUS_REPORT_INTERVAL,
    LOG_RECOVERY_ACTIONS,
    LOG_EXIT_PROXIMITY,
    EXIT_PROXIMITY_PERCENT,
    CONCISE_FORMAT,
    SHOW_MANAGEMENT_TREE,
    DETECT_ORPHANS,
    MT5_MAGIC_NUMBER,
)

# Import partial close config (if available)
try:
    from config.strategy_config import (
        PARTIAL_CLOSE_ENABLED,
        PARTIAL_CLOSE_LEVELS,
        PARTIAL_CLOSE_ORDER,
    )
except ImportError:
    # Default values if not yet in config
    PARTIAL_CLOSE_ENABLED = False
    PARTIAL_CLOSE_LEVELS = []
    PARTIAL_CLOSE_ORDER = 'recovery_first'


class ConfluenceStrategy:
    """Main trading strategy implementation"""

    def __init__(self, mt5_manager: MT5Manager):
        """
        Initialize strategy

        Args:
            mt5_manager: MT5Manager instance (already connected)
        """
        self.mt5 = mt5_manager
        self.signal_detector = SignalDetector()
        self.recovery_manager = RecoveryManager()
        self.risk_calculator = RiskCalculator()
        self.position_reporter = PositionStatusReporter()

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

        # Validate symbol list
        if not symbols:
            print("❌ Error: No symbols specified for trading")
            print("   Please provide at least one symbol (e.g., EURUSD)")
            return

        if not isinstance(symbols, list):
            print("❌ Error: Symbols must be provided as a list")
            return

        # Get account info
        account_info = self.mt5.get_account_info()
        if not account_info:
            print("❌ Failed to get account info")
            return

        print(f"Account Balance: ${account_info['balance']:.2f}")
        print(f"Account Equity: ${account_info['equity']:.2f}")
        print(f"Symbols: {', '.join(symbols)}")
        print(f"Timeframe: {TIMEFRAME}")
        print(f"HTF: {', '.join(HTF_TIMEFRAMES)}")
        print()

        # Set initial equity (not balance) for drawdown tracking
        # This ensures existing unrealized P&L doesn't count as "new" drawdown
        self.risk_calculator.set_initial_balance(account_info['equity'])

        # Adopt existing positions for crash recovery
        print("=" * 80)
        print("🔄 CRASH RECOVERY: Adopting existing positions")
        print("=" * 80)
        all_positions = self.mt5.get_all_positions()  # Get ALL positions, not filtered by magic
        if all_positions:
            print(f"Found {len(all_positions)} open position(s) in MT5")
            # Filter to only our trading symbols
            symbol_positions = [p for p in all_positions if p['symbol'] in symbols]
            if symbol_positions:
                print(f"   {len(symbol_positions)} position(s) match trading symbols: {', '.join(symbols)}")
                adopted = self.recovery_manager.adopt_existing_positions(
                    symbol_positions,
                    magic_number=None  # Adopt ALL positions for our symbols, regardless of magic number
                )
                if adopted > 0:
                    print(f"✅ Successfully adopted {adopted} position(s)")
                    print("   All positions now protected with Grid/Hedge/DCA recovery")
                else:
                    print("ℹ️  All positions are recovery orders (already linked to parents)")
            else:
                print(f"ℹ️  No positions found for symbols: {', '.join(symbols)}")
        else:
            print("ℹ️  No existing positions to adopt")
        print("=" * 80)
        print()

        self.running = True
        initial_equity = account_info['equity']
        circuit_breaker_threshold = initial_equity * 0.5  # Stop if equity drops below 50%

        try:
            while self.running:
                # Circuit breaker: Check equity before each iteration
                current_account = self.mt5.get_account_info()
                if current_account and current_account['equity'] < circuit_breaker_threshold:
                    print("\n" + "=" * 80)
                    print("🚨 CIRCUIT BREAKER TRIGGERED")
                    print("=" * 80)
                    print(f"   Initial equity: ${initial_equity:.2f}")
                    print(f"   Current equity: ${current_account['equity']:.2f}")
                    print(f"   Loss: ${initial_equity - current_account['equity']:.2f} ({((initial_equity - current_account['equity'])/initial_equity * 100):.1f}%)")
                    print(f"   Threshold: ${circuit_breaker_threshold:.2f} (50% of starting)")
                    print("   STOPPING BOT TO PREVENT FURTHER LOSSES")
                    print("=" * 80)
                    self.running = False
                    break

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
                continue

        # 4. Generate periodic status report (after processing all symbols)
        if STATUS_REPORT_ENABLED and self.position_reporter.should_report(STATUS_REPORT_INTERVAL):
            self._print_status_report()

    def _refresh_market_data(self, symbol: str):
        """Refresh market data for symbol if needed"""
        now = datetime.now()
        last_refresh = self.last_data_refresh.get(symbol)

        # Check if refresh needed
        if last_refresh:
            minutes_since = (now - last_refresh).total_seconds() / 60
            if minutes_since < DATA_REFRESH_INTERVAL:
                return  # Data still fresh

        # Fetch H1 data
        print(f"📊 Fetching {symbol} data...", end='', flush=True)
        h1_data = self.mt5.get_historical_data(symbol, TIMEFRAME, bars=500)
        if h1_data is None:
            print(" ❌ Failed")
            return

        # Calculate VWAP on H1 data
        h1_data = self.signal_detector.vwap.calculate(h1_data)

        # Fetch HTF data
        d1_data = self.mt5.get_historical_data(symbol, 'D1', bars=100)
        w1_data = self.mt5.get_historical_data(symbol, 'W1', bars=50)
        print(" ✅ Complete", flush=True)

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

                # Calculate proper pip value (not point!)
                # For most forex pairs: pip = point * 10 (5 decimal vs 4 decimal)
                # For JPY pairs: pip = point * 100 (3 decimal vs 2 decimal)
                point = symbol_info.get('point', 0.00001)
                digits = symbol_info.get('digits', 5)

                # Standard forex pairs (5 digits): 1 pip = 10 points
                # JPY pairs (3 digits): 1 pip = 100 points
                if digits == 5 or digits == 3:
                    pip_value = point * 10
                else:
                    pip_value = point

                recovery_actions = self.recovery_manager.check_all_recovery_triggers(
                    ticket, current_price, pip_value
                )

                # Execute recovery actions
                for action in recovery_actions:
                    self._execute_recovery_action(action)

                # Check exit conditions (only for tracked original positions)
                # Priority order: 0) Partial close, 1) Full profit target, 2) Time limit, 3) VWAP reversion

                # Get account info for profit target calculation
                account_info = self.mt5.get_account_info()
                all_positions = self.mt5.get_positions()

                # 0. Check partial close triggers (lock in profits incrementally)
                if account_info and PARTIAL_CLOSE_ENABLED:
                    partial_close_config = {
                        'enabled': PARTIAL_CLOSE_ENABLED,
                        'levels': PARTIAL_CLOSE_LEVELS,
                        'close_order': PARTIAL_CLOSE_ORDER,
                    }

                    partial_close_action = self.recovery_manager.check_partial_close_trigger(
                        ticket=ticket,
                        mt5_positions=all_positions,
                        account_balance=account_info['balance'],
                        profit_target_percent=PROFIT_TARGET_PERCENT,
                        partial_close_config=partial_close_config
                    )

                    if partial_close_action:
                        self._execute_partial_close(ticket, partial_close_action, all_positions)
                        # Don't continue - allow further checks after partial close

                # 1. Check full profit target (from config)
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

        cache = self.market_data_cache[symbol]
        h1_data = cache['h1']
        d1_data = cache['d1']
        w1_data = cache['w1']

        # Detect signal
        signal = self.signal_detector.detect_signal(
            current_data=h1_data,
            daily_data=d1_data,
            weekly_data=w1_data,
            symbol=symbol
        )

        if signal is None:
            return

        # Signal detected!
        self.stats['signals_detected'] += 1

        print()
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

    def _execute_partial_close(
        self,
        original_ticket: int,
        partial_action: Dict,
        all_positions: List[Dict]
    ):
        """
        Execute partial close of recovery stack

        Args:
            original_ticket: Original position ticket
            partial_action: Partial close action from recovery_manager
            all_positions: All current MT5 positions
        """
        trigger_percent = partial_action['trigger_percent']
        close_percent = partial_action['close_percent']

        # Get positions to close (now returns List[Dict] with ticket, volume, partial)
        positions_to_close = self.recovery_manager.get_partial_close_tickets(
            ticket=original_ticket,
            close_percent=close_percent,
            mt5_positions=all_positions,
            close_order=PARTIAL_CLOSE_ORDER
        )

        if not positions_to_close:
            print(f"⚠️ No positions available for partial close of {original_ticket}")
            return

        # Calculate total volume to close for display
        total_close_volume = sum(p['volume'] for p in positions_to_close)

        print(f"💰 Executing partial close for {original_ticket}")
        print(f"   Trigger: {trigger_percent}% profit level")
        print(f"   Closing {close_percent}% of stack ({total_close_volume:.3f} lots)")

        closed_count = 0
        closed_volume = 0.0
        closed_tickets = []

        for close_instruction in positions_to_close:
            ticket = close_instruction['ticket']
            volume = close_instruction['volume']
            is_partial = close_instruction['partial']

            # Close the position (full or partial volume)
            if self.mt5.close_position(ticket, volume=volume):
                closed_count += 1
                closed_volume += volume
                closed_tickets.append(ticket)
                self.stats['trades_closed'] += 1

                partial_str = " (partial)" if is_partial else ""
                print(f"   ✅ Closed #{ticket}: {volume:.3f} lots{partial_str}")
            else:
                print(f"   ❌ Failed to close #{ticket}")

        # Record partial close (pass ticket numbers only)
        self.recovery_manager.record_partial_close(
            ticket=original_ticket,
            trigger_level=trigger_percent,
            closed_tickets=closed_tickets,
            closed_volume=closed_volume
        )

        print(f"💰 Partial close complete: {closed_count}/{len(positions_to_close)} positions")
        print(f"   Volume closed: {closed_volume:.3f} lots")
        print(f"   Remaining stack positions tracking...")

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

            # Log recovery action (if enabled)
            if LOG_RECOVERY_ACTIONS:
                recovery_msg = self.position_reporter.format_recovery_action(
                    action_type=action_type,
                    ticket=original_ticket,
                    details=action
                )
                print(recovery_msg)

    def _print_status_report(self):
        """Print periodic status report for all positions"""
        try:
            # Get all positions and account info
            all_positions = self.mt5.get_positions()
            account_info = self.mt5.get_account_info()

            if not all_positions or not account_info:
                return

            # Generate and print report
            report = self.position_reporter.generate_status_report(
                positions=all_positions,
                recovery_manager=self.recovery_manager,
                account_info=account_info,
                profit_target_percent=PROFIT_TARGET_PERCENT,
                max_hold_hours=MAX_POSITION_HOURS,
                concise=CONCISE_FORMAT
            )

            print(report)

            # Show management tree if enabled (shows parent-child relationships)
            if SHOW_MANAGEMENT_TREE:
                print("\n" + "─"*80)
                print("🌳 POSITION MANAGEMENT TREES")
                print("─"*80)

                # Get tracked positions (managed positions)
                tracked_tickets = set(self.recovery_manager.tracked_positions.keys())

                for position in all_positions:
                    if position['ticket'] in tracked_tickets:
                        tree = self.position_reporter.generate_management_tree(
                            parent_position=position,
                            recovery_manager=self.recovery_manager,
                            all_mt5_positions=all_positions
                        )
                        print(f"\n{tree}")

                print("─"*80)

            # Check for exit proximity alerts (if enabled)
            # Only alert on MANAGED positions that will actually close
            if LOG_EXIT_PROXIMITY:
                tracked_tickets = self.recovery_manager.tracked_positions.keys()

                for position in all_positions:
                    ticket = position['ticket']

                    # Only check parent/managed positions, not recovery trades
                    if ticket not in tracked_tickets:
                        continue

                    # For managed positions, check STACK total profit
                    stack_profit = self.recovery_manager.calculate_net_profit(ticket, all_positions)
                    if stack_profit is not None:
                        # Use stack total for alert calculation
                        profit_target = account_info['balance'] * (PROFIT_TARGET_PERCENT / 100)
                        profit_percent = (stack_profit / profit_target * 100) if profit_target > 0 else 0

                        if profit_percent >= EXIT_PROXIMITY_PERCENT:
                            print(f"[ALERT] APPROACHING TARGET - Position #{ticket} at {profit_percent:.0f}% of profit target (${stack_profit:.2f}/${profit_target:.2f})")
                    else:
                        # Standalone position - use individual profit
                        alert = self.position_reporter.check_exit_proximity(
                            position=position,
                            account_balance=account_info['balance'],
                            profit_target_percent=PROFIT_TARGET_PERCENT,
                            proximity_threshold=EXIT_PROXIMITY_PERCENT
                        )
                        if alert:
                            print(alert)

        except Exception as e:
            print(f"❌ Error generating status report: {e}")

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
