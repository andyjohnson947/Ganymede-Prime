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
from strategies.stack_limiter import StackDrawdownLimiter
from indicators.advanced_regime_detector import AdvancedRegimeDetector
from utils.risk_calculator import RiskCalculator
from utils.config_reloader import reload_config, print_current_config
from utils.position_reporter import PositionStatusReporter
from diagnostics.diagnostic_module import DiagnosticModule
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
    MAX_STACK_DRAWDOWN_USD,
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
        self.stack_limiter = StackDrawdownLimiter(max_drawdown_usd=MAX_STACK_DRAWDOWN_USD)
        self.regime_detector = AdvancedRegimeDetector()  # Hurst + VHF regime detection
        self.risk_calculator = RiskCalculator()
        self.position_reporter = PositionStatusReporter()

        # Initialize diagnostic module for trading intelligence
        self.diagnostic_module = DiagnosticModule(
            mt5_manager=self.mt5,
            recovery_manager=self.recovery_manager,
            data_dir="data/diagnostics"
        )

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

        # Store signal data for diagnostic tracking
        # Maps ticket -> signal data (confluence factors, breakout info, etc.)
        self.signal_data_by_ticket = {}

        # Circuit breaker for stack drawdown limit
        self.trading_suspended = False
        self.suspension_reason = None
        self.suspension_time = None

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

        # Start diagnostic module for hourly analysis
        print("=" * 80)
        print("📊 DIAGNOSTIC MODULE")
        print("=" * 80)
        self.diagnostic_module.start()
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

        # Stop diagnostic module
        self.diagnostic_module.stop()

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
                import traceback
                print(f"❌ Error processing {symbol}: {e}")
                traceback.print_exc()
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

        # Fetch H1 data (for signal detection)
        print(f"📊 Fetching {symbol} data...", end='', flush=True)
        h1_data = self.mt5.get_historical_data(symbol, TIMEFRAME, bars=500)
        if h1_data is None:
            print(" ❌ Failed")
            return

        # Calculate VWAP on H1 data
        h1_data = self.signal_detector.vwap.calculate(h1_data)

        # Fetch M15 data (for regime detection - more responsive for intraday)
        m15_data = self.mt5.get_historical_data(symbol, 'M15', bars=500)
        if m15_data is None:
            print(" ❌ Failed to fetch M15")
            return

        # Fetch HTF data
        d1_data = self.mt5.get_historical_data(symbol, 'D1', bars=100)
        w1_data = self.mt5.get_historical_data(symbol, 'W1', bars=50)
        print(" ✅ Complete", flush=True)

        if d1_data is None or w1_data is None:
            return

        # Cache the data
        self.market_data_cache[symbol] = {
            'h1': h1_data,        # For signal detection (VWAP/confluence)
            'm15': m15_data,      # For regime detection (Hurst/VHF)
            'd1': d1_data,
            'w1': w1_data,
            'last_update': now
        }

        self.last_data_refresh[symbol] = now

    def _manage_positions(self, symbol: str):
        """Manage existing positions for symbol"""
        positions = self.mt5.get_positions(symbol)

        # ORPHAN DETECTION: Check for and close orphaned recovery trades
        # This runs once per symbol check to prevent orphans from accumulating
        all_positions = self.mt5.get_positions()
        if all_positions:
            self.recovery_manager.close_orphaned_positions(self.mt5, all_positions)

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
                # Get data needed for both strategies
                tracked_info = self.recovery_manager.tracked_positions[ticket]
                strategy_mode = tracked_info.get('metadata', {}).get('strategy_mode', 'mean_reversion')
                account_info = self.mt5.get_account_info()
                all_positions = self.mt5.get_positions()

                # Check strategy mode - skip Grid/Hedge/DCA for breakout trades
                if strategy_mode == 'breakout':
                    # Breakout trades skip recovery mechanisms (Grid/Hedge/DCA)
                    # They use SL/TP + partial close only
                    pass
                else:
                    # Mean reversion trades use recovery mechanisms
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

                    # REGIME CHECK: Only allow recovery in ranging/choppy markets
                    # Use M15 for intraday regime detection (more responsive than H1)
                    m15_data = self.market_data_cache.get(symbol, {}).get('m15')
                    recovery_allowed = True

                    if m15_data is not None and not m15_data.empty:
                        is_safe, reason = self.regime_detector.is_safe_for_recovery(m15_data, min_confidence=0.60)
                        if not is_safe:
                            recovery_allowed = False
                            regime_info = self.regime_detector.detect_regime(m15_data)

                            # Calculate current stack loss
                            current_stack_pnl = self.recovery_manager.calculate_net_profit(ticket, all_positions)
                            current_loss = abs(current_stack_pnl) if current_stack_pnl and current_stack_pnl < 0 else 0.0

                            print(f"\n⚠️  RECOVERY BLOCKED - {symbol} #{ticket}")
                            print(f"   Regime: {regime_info['regime'].upper()} (H: {regime_info['hurst']:.3f}, VHF: {regime_info['vhf']:.3f})")
                            print(f"   {reason}")
                            print(f"   Current stack loss: ${current_loss:.2f}")

                            # HYBRID EMERGENCY SL: If already losing $50+, set hard SL immediately
                            if current_loss >= 50.0:
                                emergency_sl = self._calculate_emergency_sl(
                                    ticket=ticket,
                                    position=position,
                                    symbol_info=symbol_info,
                                    all_positions=all_positions,
                                    max_loss_usd=100.0
                                )

                                if emergency_sl:
                                    # Set the emergency SL on the parent position
                                    success = self._set_emergency_sl(ticket, emergency_sl, symbol)
                                    if success:
                                        print(f"   🛑 EMERGENCY SL SET: {emergency_sl:.5f} (limits loss to ~$100)")
                                    else:
                                        print(f"   ⚠️  Failed to set emergency SL - monitoring with $100 soft limit")
                                else:
                                    print(f"   ⚠️  Could not calculate emergency SL - monitoring with $100 soft limit")
                            else:
                                print(f"   ⏸️  Loss < $50 - monitoring with $100 soft limit (no hard SL)")

                            print()

                    if recovery_allowed:
                        recovery_actions = self.recovery_manager.check_all_recovery_triggers(
                            ticket, current_price, pip_value, all_positions=all_positions
                        )

                        # Execute recovery actions
                        for action in recovery_actions:
                            self._execute_recovery_action(action)

                    # STACK DRAWDOWN LIMIT: Check if stack exceeded $100 loss limit
                    self._check_stack_drawdown_limit(ticket, all_positions)

                # Check exit conditions (for BOTH strategies - mean reversion AND breakout)
                # Priority order: 0) Partial close, 1) Full profit target, 2) Time limit, 3) VWAP reversion

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

            # 3. Check exit signal (VWAP reversion) - only for mean reversion trades
            # Breakout trades rely on SL/TP, not VWAP reversion
            tracked_info = self.recovery_manager.tracked_positions.get(ticket, {})
            strategy_mode = tracked_info.get('metadata', {}).get('strategy_mode', 'mean_reversion')

            if strategy_mode == 'mean_reversion' and symbol in self.market_data_cache:
                h1_data = self.market_data_cache[symbol]['h1']
                should_exit = self.signal_detector.check_exit_signal(position, h1_data)

                if should_exit:
                    print(f"🎯 Exit signal detected for {ticket} - VWAP reversion")
                    # Close entire stack (parent + all recovery trades)
                    self._close_recovery_stack(ticket)

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

        # Check if trading is suspended
        if not self._check_trading_suspension(symbol):
            print(f"🛑 Trading suspended for {symbol}")
            print(f"   Reason: {self.suspension_reason}")
            print(f"   Waiting for market to return to RANGING regime")
            return

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

        # Validate trade (pass mt5 for emergency close if drawdown exceeded)
        can_trade, reason = self.risk_calculator.validate_trade(
            account_info=account_info,
            symbol_info=symbol_info,
            volume=volume,
            current_positions=positions,
            mt5_manager=self.mt5
        )

        if not can_trade:
            print(f"❌ Trade validation failed: {reason}")
            return

        # Place order with appropriate risk management based on strategy mode
        strategy_mode = signal.get('strategy_mode', 'mean_reversion')

        if strategy_mode == 'breakout':
            # Breakout trades use confluence level as SL, 3R TP
            sl = signal.get('stop_loss')
            tp = signal.get('take_profit')
            reward_ratio = signal.get('reward_ratio', 3.0)
            comment = f"Breakout:{signal['confluence_score']}"
            print(f"📊 Strategy: Breakout (Confluence-based SL/TP)")
            print(f"   SL: {sl:.5f} | TP: {tp:.5f} ({reward_ratio}R)")
        else:
            # Mean reversion uses VWAP reversion (no hard SL/TP)
            sl = None
            tp = None
            comment = f"Confluence:{signal['confluence_score']}"
            print(f"📊 Strategy: Mean Reversion (VWAP-based exits)")

        ticket = self.mt5.place_order(
            symbol=symbol,
            order_type=direction,
            volume=volume,
            sl=sl,
            tp=tp,
            comment=comment
        )

        if ticket:
            self.stats['trades_opened'] += 1
            print(f"✅ Trade opened: Ticket {ticket}")

            # Store signal data for diagnostic tracking
            self.signal_data_by_ticket[ticket] = {
                'confluence_score': signal.get('confluence_score', 0),
                'confluence_factors': signal.get('factors', []),
                'strategy_mode': strategy_mode,
                'breakout_info': signal.get('breakout', {}),
                'htf_signals': signal.get('htf_signals', {}),
                'entry_time': datetime.now().isoformat(),
                'symbol': symbol,
                'direction': direction,
            }

            # Start tracking for recovery
            self.recovery_manager.track_position(
                ticket=ticket,
                symbol=symbol,
                entry_price=price,
                position_type=direction,
                volume=volume,
                metadata={'strategy_mode': strategy_mode}  # Track strategy mode
            )

    def _close_recovery_stack(self, original_ticket: int):
        """
        Close entire recovery stack (original + grid + hedge + DCA)

        Args:
            original_ticket: Original position ticket
        """
        # Get all tickets in the stack
        stack_tickets = self.recovery_manager.get_all_stack_tickets(original_ticket)

        # Get position data before closing for diagnostic recording
        all_positions = self.mt5.get_positions()
        parent_position = None
        for pos in all_positions:
            if pos['ticket'] == original_ticket:
                parent_position = pos
                break

        print(f"📦 Closing recovery stack for {original_ticket}")
        print(f"   Closing {len(stack_tickets)} positions...")

        # Calculate total profit before closing
        total_profit = self.recovery_manager.calculate_net_profit(original_ticket, all_positions) or 0.0

        closed_count = 0
        failed_tickets = []

        # First attempt to close all positions
        for ticket in stack_tickets:
            if self.mt5.close_position(ticket):
                closed_count += 1
                self.stats['trades_closed'] += 1
                print(f"   ✅ Closed #{ticket}")
            else:
                print(f"   ❌ Failed to close #{ticket}")
                failed_tickets.append(ticket)

        # FIX 3: Retry failed closes once (prevents orphaned hedges from close failures)
        if failed_tickets:
            print(f"   🔄 Retrying {len(failed_tickets)} failed close(s)...")
            time.sleep(1)  # Brief pause before retry

            for ticket in failed_tickets:
                if self.mt5.close_position(ticket):
                    closed_count += 1
                    self.stats['trades_closed'] += 1
                    print(f"   ✅ Retry successful: #{ticket}")
                    failed_tickets.remove(ticket)
                else:
                    print(f"   ❌ Retry failed: #{ticket}")

        # Record trade close with diagnostic module
        if parent_position:
            trade_data = {
                'ticket': original_ticket,
                'symbol': parent_position['symbol'],
                'type': 'buy' if parent_position['type'] == 0 else 'sell',
                'volume': parent_position['volume'],
                'profit': total_profit,
                'open_time': parent_position.get('time', datetime.now()).isoformat() if isinstance(parent_position.get('time'), datetime) else str(parent_position.get('time', '')),
                'close_time': datetime.now().isoformat(),
                'stack_size': len(stack_tickets),
            }

            # Add confluence signal data if available
            signal_data = self.signal_data_by_ticket.get(original_ticket, {})
            if signal_data:
                trade_data['confluence_score'] = signal_data.get('confluence_score', 0)
                trade_data['confluence_factors'] = signal_data.get('confluence_factors', [])
                trade_data['strategy_mode'] = signal_data.get('strategy_mode', 'unknown')
                trade_data['breakout_info'] = signal_data.get('breakout_info', {})
                trade_data['htf_signals'] = signal_data.get('htf_signals', {})

                # Clean up stored signal data
                del self.signal_data_by_ticket[original_ticket]

            self.diagnostic_module.record_trade_close(trade_data)

        print(f"📦 Stack closed: {closed_count}/{len(stack_tickets)} positions")

        # CRITICAL: Verify all positions actually closed before untracking
        all_positions_after = self.mt5.get_positions()
        still_open = []
        if all_positions_after:
            for ticket in stack_tickets:
                if any(pos['ticket'] == ticket for pos in all_positions_after):
                    still_open.append(ticket)
                    print(f"   ⚠️  Position #{ticket} still open despite close command!")

        # If any positions failed to close, try force close
        if still_open:
            print(f"   🔨 FORCE CLOSE: Attempting to close {len(still_open)} positions that survived...")
            for ticket in still_open:
                # Get current position to check if it's still there
                pos_still_there = any(p['ticket'] == ticket for p in self.mt5.get_positions() or [])
                if pos_still_there:
                    # Try close with multiple attempts
                    for attempt in range(3):
                        if self.mt5.close_position(ticket):
                            print(f"   ✅ Force closed #{ticket} on attempt {attempt + 1}")
                            still_open.remove(ticket)
                            break
                        time.sleep(0.5)
                    else:
                        print(f"   ❌ CRITICAL: Position #{ticket} could not be force closed - will become orphan")

        # Only untrack parent AFTER confirming all positions closed
        if not still_open:
            self.recovery_manager.untrack_position(original_ticket)
            print(f"   ✅ Parent #{original_ticket} untracked - all stack positions confirmed closed")
        else:
            # DO NOT untrack if positions still open - this prevents orphan adoption
            print(f"   ⚠️  Parent #{original_ticket} kept tracked - {len(still_open)} positions still open")
            # Immediate orphan cleanup for the positions that failed
            orphan_count = self.recovery_manager.close_orphaned_positions(self.mt5, self.mt5.get_positions())
            if orphan_count > 0:
                print(f"   🧹 Emergency cleanup: closed {orphan_count} orphan(s)")

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

        # DIRECTION VALIDATION: Ensure recovery trade direction is correct
        is_valid, error_msg = self.recovery_manager.validate_recovery_direction(action)
        if not is_valid:
            print(f"❌ DIRECTION VALIDATION FAILED: {error_msg}")
            print(f"   Blocking {action_type} trade to prevent direction mismatch bug")
            return

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

            # Record recovery action with diagnostic module
            # Calculate current stack metrics for tracking
            all_positions = self.mt5.get_positions()
            stack_drawdown = 0.0
            stack_total_volume = 0.0

            if all_positions and original_ticket:
                # Calculate net P&L and total volume for entire stack
                stack_drawdown = self.recovery_manager.calculate_net_profit(
                    original_ticket, all_positions
                ) or 0.0

                # Get total volume from tracked position
                if original_ticket in self.recovery_manager.tracked_positions:
                    stack_total_volume = self.recovery_manager.tracked_positions[original_ticket].get('total_volume', 0.0)

            recovery_data = {
                'type': action_type,
                'parent_ticket': original_ticket,
                'recovery_ticket': ticket,
                'symbol': symbol,
                'volume': volume,
                'level': action.get('level', 1),
                'trigger_time': datetime.now().isoformat(),
                'drawdown': stack_drawdown,  # Current stack P&L (negative = loss)
                'total_volume': stack_total_volume,  # Total stack exposure
            }
            self.diagnostic_module.record_recovery_action(recovery_data)

            # Log recovery action (if enabled)
            if LOG_RECOVERY_ACTIONS:
                recovery_msg = self.position_reporter.format_recovery_action(
                    action_type=action_type,
                    ticket=original_ticket,
                    details=action
                )
                print(recovery_msg)

    def _calculate_emergency_sl(
        self,
        ticket: int,
        position: Dict,
        symbol_info: Dict,
        all_positions: List[Dict],
        max_loss_usd: float
    ) -> Optional[float]:
        """
        Calculate emergency stop loss price that limits total stack loss to max_loss_usd

        Args:
            ticket: Parent position ticket
            position: Position dict from MT5
            symbol_info: Symbol info from MT5
            all_positions: All current positions
            max_loss_usd: Maximum allowed loss in USD (e.g., 100.0)

        Returns:
            Stop loss price or None if calculation fails
        """
        try:
            # Get current stack P&L
            current_pnl = self.recovery_manager.calculate_net_profit(ticket, all_positions)
            if current_pnl is None:
                return None

            current_loss = abs(current_pnl) if current_pnl < 0 else 0.0

            # Calculate remaining loss buffer
            remaining_loss_buffer = max_loss_usd - current_loss

            if remaining_loss_buffer <= 0:
                # Already exceeded target - set SL at current price
                return position['price_current']

            # Get position details
            position_type = position['type']  # 0 = buy, 1 = sell
            entry_price = position['price_open']
            current_price = position['price_current']
            volume = position['volume']

            # Get symbol info for pip calculation
            point = symbol_info.get('point', 0.00001)
            contract_size = symbol_info.get('contract_size', 100000)
            digits = symbol_info.get('digits', 5)

            # Calculate pip value
            if digits == 5 or digits == 3:
                pip = point * 10
            else:
                pip = point

            # Calculate dollar value per pip
            # For forex: pip_value = (pip * contract_size * volume)
            pip_value_usd = pip * contract_size * volume

            # Calculate pips needed to hit max loss
            pips_to_max_loss = remaining_loss_buffer / pip_value_usd if pip_value_usd > 0 else 0

            # Calculate SL price
            if position_type == 0:  # BUY position
                # SL below current price
                sl_price = current_price - (pips_to_max_loss * pip)
            else:  # SELL position
                # SL above current price
                sl_price = current_price + (pips_to_max_loss * pip)

            # Validate SL is on correct side of entry
            if position_type == 0:  # BUY
                if sl_price > entry_price:
                    # SL would be above entry (wrong side)
                    sl_price = entry_price - (10 * pip)  # Set 10 pips below entry as fallback
            else:  # SELL
                if sl_price < entry_price:
                    # SL would be below entry (wrong side)
                    sl_price = entry_price + (10 * pip)  # Set 10 pips above entry as fallback

            return float(sl_price)

        except Exception as e:
            print(f"⚠️  Error calculating emergency SL: {e}")
            return None

    def _set_emergency_sl(self, ticket: int, sl_price: float, symbol: str) -> bool:
        """
        Set emergency stop loss on a position

        Args:
            ticket: Position ticket
            sl_price: Stop loss price
            symbol: Trading symbol

        Returns:
            bool: True if successful
        """
        try:
            # Get position info
            positions = self.mt5.get_positions()
            if not positions:
                return False

            position = None
            for pos in positions:
                if pos['ticket'] == ticket:
                    position = pos
                    break

            if not position:
                print(f"⚠️  Position {ticket} not found for SL modification")
                return False

            # Get symbol info for validation
            symbol_info = self.mt5.get_symbol_info(symbol)
            if not symbol_info:
                return False

            # Validate SL against broker requirements
            point = symbol_info.get('point', 0.00001)
            stops_level = symbol_info.get('trade_stops_level', 0)
            current_price = position['price_current']

            # Check minimum distance
            sl_distance = abs(current_price - sl_price) / point
            if sl_distance < stops_level:
                print(f"⚠️  SL too close to current price ({sl_distance:.0f} < {stops_level} points)")
                # Adjust to minimum distance
                if position['type'] == 0:  # BUY
                    sl_price = current_price - (stops_level * point)
                else:  # SELL
                    sl_price = current_price + (stops_level * point)

            # Use MT5 manager to modify position
            import MetaTrader5 as mt5

            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": symbol,
                "position": ticket,
                "sl": sl_price,
                "tp": position.get('tp', 0.0),  # Keep existing TP if any
            }

            result = mt5.order_send(request)

            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                return True
            else:
                if result:
                    print(f"⚠️  SL modification failed: {result.comment} (retcode: {result.retcode})")
                else:
                    print(f"⚠️  SL modification failed: {mt5.last_error()}")
                return False

        except Exception as e:
            print(f"⚠️  Error setting emergency SL: {e}")
            return False

    def _check_stack_drawdown_limit(self, ticket: int, all_positions: List[Dict]):
        """
        Check if stack has exceeded drawdown limit and take action

        Args:
            ticket: Parent position ticket
            all_positions: All current MT5 positions
        """
        if ticket not in self.recovery_manager.tracked_positions:
            return

        # Calculate current stack P&L
        current_pnl = self.recovery_manager.calculate_net_profit(ticket, all_positions)
        if current_pnl is None:
            return

        # Check if recovery is active for this stack
        tracked = self.recovery_manager.tracked_positions[ticket]
        has_recovery = (
            len(tracked.get('grid_levels', [])) > 0 or
            len(tracked.get('hedge_tickets', [])) > 0 or
            len(tracked.get('dca_levels', [])) > 0
        )

        # Get symbol for reporting
        symbol = tracked.get('symbol', 'UNKNOWN')

        # Check limit with smart recovery-aware logic
        limit_check = self.stack_limiter.check_stack_limit(
            ticket=ticket,
            current_drawdown=current_pnl,
            recovery_active=has_recovery,
            symbol=symbol
        )

        status = limit_check['status']
        action = limit_check['action']

        # Log if in warning/critical zone
        if status != 'safe':
            print(f"\n{'='*80}")
            print(f"⚠️  STACK DRAWDOWN LIMIT CHECK - {symbol} #{ticket}")
            print(f"{'='*80}")
            print(f"   Status: {status.upper().replace('_', ' ')}")
            print(f"   {limit_check['message']}")

        # Take action if needed
        if action == 'close_stack':
            print(f"\n🚨 EMERGENCY STACK CLOSE TRIGGERED")
            print(f"   Reason: {limit_check.get('reason', 'limit_exceeded')}")
            print(f"   Closing entire stack for #{ticket}...")

            # Close the stack
            self._close_recovery_stack(ticket)

            # Reset stack tracking
            self.stack_limiter.reset_stack(ticket)

            # Suspend trading until market returns to ranging
            self.trading_suspended = True
            self.suspension_reason = f"Stack #{ticket} exceeded ${limit_check['current_loss']:.2f} limit"
            self.suspension_time = datetime.now()

            print(f"\n🛑 TRADING SUSPENDED")
            print(f"   Reason: {self.suspension_reason}")
            print(f"   Will resume when market regime returns to RANGING")
            print(f"{'='*80}\n")

        elif action == 'monitor':
            print(f"   Action: Monitoring - recovery has room to work")
            print(f"{'='*80}\n")

    def _check_trading_suspension(self, symbol: str) -> bool:
        """
        Check if trading should resume based on market regime (Hurst + VHF on M15)

        Args:
            symbol: Trading symbol to check

        Returns:
            bool: True if trading can proceed, False if still suspended
        """
        if not self.trading_suspended:
            return True

        # Check market regime for the symbol
        if symbol not in self.market_data_cache:
            return False

        cache = self.market_data_cache[symbol]
        m15_data = cache.get('m15')  # Use M15 for intraday regime detection

        if m15_data is None or m15_data.empty:
            return False

        # Use advanced regime detector (Hurst + VHF on M15)
        is_safe, reason = self.regime_detector.is_safe_for_recovery(m15_data, min_confidence=0.65)

        # Resume trading if market is SAFE for recovery (ranging/choppy)
        if is_safe:
            regime_info = self.regime_detector.detect_regime(m15_data)

            print(f"\n{'='*80}")
            print(f"✅ TRADING SUSPENSION LIFTED")
            print(f"{'='*80}")
            print(f"   Regime: {regime_info['regime'].upper()} (confidence: {regime_info['confidence']:.0%})")
            print(f"   Hurst Exponent: {regime_info['hurst']:.3f} (< 0.5 = mean reverting)")
            print(f"   VHF: {regime_info['vhf']:.3f} (< 0.40 = ranging)")
            print(f"   VHF Trend: {regime_info.get('vhf_trend', 'unknown')}")
            print(f"   Suspended since: {self.suspension_time.strftime('%Y-%m-%d %H:%M:%S') if self.suspension_time else 'N/A'}")
            print(f"   Previous reason: {self.suspension_reason}")
            print(f"   Reason: {reason}")
            print(f"   Trading resuming for {symbol}...")
            print(f"{'='*80}\n")

            self.trading_suspended = False
            self.suspension_reason = None
            self.suspension_time = None
            return True
        else:
            # Still trending or VHF rising - keep trading suspended
            regime_info = self.regime_detector.detect_regime(h1_data)
            print(f"🛑 Trading still suspended for {symbol}")
            print(f"   Current regime: {regime_info['regime'].upper()} (confidence: {regime_info['confidence']:.0%})")
            print(f"   Hurst: {regime_info['hurst']:.3f}, VHF: {regime_info['vhf']:.3f}")
            print(f"   Reason: {reason}")
            return False

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

            # Show current market regime for all symbols
            print("\n" + "="*80)
            print("📊 MARKET REGIME STATUS (Hurst + VHF on M15)")
            print("="*80)

            for symbol in SYMBOLS:
                if symbol in self.market_data_cache:
                    m15_data = self.market_data_cache[symbol].get('m15')
                    if m15_data is not None and not m15_data.empty:
                        regime_info = self.regime_detector.detect_regime(m15_data)
                        is_safe, reason = self.regime_detector.is_safe_for_recovery(m15_data, min_confidence=0.60)

                        # Color code based on safety
                        status_icon = "✅" if is_safe else "⚠️"

                        print(f"\n{status_icon} {symbol}")
                        print(f"   Regime: {regime_info['regime'].upper()} (confidence: {regime_info['confidence']:.0%})")
                        print(f"   Hurst: {regime_info['hurst']:.3f} {'(mean reverting)' if regime_info['hurst'] < 0.5 else '(trending)'}")
                        print(f"   VHF: {regime_info['vhf']:.3f} {'(ranging)' if regime_info['vhf'] < 0.40 else '(trending)'}")
                        print(f"   VHF Trend: {regime_info.get('vhf_trend', 'unknown').upper()}")
                        print(f"   Recovery: {'ALLOWED' if is_safe else 'BLOCKED'}")
                        if not is_safe:
                            print(f"   Reason: {reason}")

            print("="*80 + "\n")

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

        # Get diagnostic status
        diagnostic_status = self.diagnostic_module.get_current_status()

        return {
            'running': self.running,
            'account': account_info,
            'risk_metrics': risk_metrics,
            'positions': positions,
            'recovery_status': recovery_status,
            'statistics': self.stats,
            'cached_symbols': list(self.market_data_cache.keys()),
            'diagnostics': diagnostic_status,
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
