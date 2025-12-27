"""
Main Confluence Strategy
Orchestrates signal detection, position management, and recovery
"""

import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import time

from ..core.mt5_manager import MT5Manager
from .signal_detector import SignalDetector
from .recovery_manager import RecoveryManager
from .time_filters import TimeFilter
from .breakout_strategy import BreakoutStrategy
from .partial_close_manager import PartialCloseManager
from ..utils.risk_calculator import RiskCalculator
from ..utils.config_reloader import reload_config, print_current_config
from ..utils.timezone_manager import get_current_time
from ..utils.logger import logger
from ..portfolio.portfolio_manager import PortfolioManager
from ..indicators.adx import calculate_adx, analyze_candle_direction
from ..indicators.hurst import calculate_hurst_exponent, combine_hurst_adx_analysis
from ..config.strategy_config import (
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
    LOOP_INTERVAL_SECONDS,
    DEFAULT_TP_PIPS,
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
        self.symbol_blacklist = {}  # Track temporarily blacklisted symbols

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
        logger.info("=" * 80)
        logger.info("CONFLUENCE STRATEGY STARTING")
        logger.info("=" * 80)

        # Get account info
        account_info = self.mt5.get_account_info()
        if not account_info:
            logger.error("Failed to get account info")
            return

        logger.info(f"Account Balance: ${account_info['balance']:.2f}")
        logger.info(f"Symbols: {', '.join(symbols)}")
        logger.info(f"Timeframe: {TIMEFRAME}")
        logger.info(f"HTF: {', '.join(HTF_TIMEFRAMES)}")

        # Set initial balance for drawdown tracking
        self.risk_calculator.set_initial_balance(account_info['balance'])

        self.running = True

        try:
            while self.running:
                # Main trading loop
                self._trading_loop(symbols)

                # Sleep before next iteration
                time.sleep(LOOP_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            logger.warning("Strategy stopped by user")
        except Exception as e:
            logger.error(f"Strategy error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop()

    def stop(self):
        """Stop the strategy"""
        self.running = False
        logger.info("=" * 80)
        logger.info("STRATEGY STATISTICS")
        logger.info("=" * 80)
        for key, value in self.stats.items():
            logger.info(f"{key.replace('_', ' ').title()}: {value}")

    def run_once(self, symbols: Optional[List[str]] = None):
        """
        Run one iteration of the trading loop (for backtesting)

        Args:
            symbols: List of symbols to trade (defaults to SYMBOLS from config)
        """
        if symbols is None:
            symbols = SYMBOLS
        self._trading_loop(symbols)

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
                logger.error(f"Error processing {symbol}: {e}")
                import traceback
                traceback.print_exc()
                continue

    def _refresh_market_data(self, symbol: str):
        """Refresh market data for symbol if needed"""
        now = get_current_time()
        last_refresh = self.last_data_refresh.get(symbol)

        # In test_mode (backtesting), always refresh data
        # In live mode, check if refresh needed
        if not self.test_mode:
            if last_refresh:
                minutes_since = (now - last_refresh).total_seconds() / 60
                if minutes_since < DATA_REFRESH_INTERVAL:
                    return  # Data still fresh

        # Fetch H1 data with error handling
        try:
            h1_data = self.mt5.get_historical_data(symbol, TIMEFRAME, bars=1000)
            if h1_data is None:
                logger.warning(f"Failed to fetch H1 data for {symbol}")
                return

            if self.test_mode:
                logger.debug(f"Refreshed H1 data for {symbol}: {len(h1_data)} bars")

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
            d1_data = self.mt5.get_historical_data(symbol, 'D1', bars=200)
            w1_data = self.mt5.get_historical_data(symbol, 'W1', bars=100)

            if d1_data is None or w1_data is None:
                logger.warning(f"Failed to fetch HTF data for {symbol}")
                return

        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            import traceback
            traceback.print_exc()
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
                        logger.info(f"Closing negative position {ticket} - {action.reason}")
                        if self.mt5.close_position(ticket):
                            self.recovery_manager.untrack_position(ticket)
                            self.stats['trades_closed'] += 1

        for position in positions:
            ticket = position['ticket']
            comment = position.get('comment', '')

            # CRITICAL FIX: Don't track recovery orders as new positions
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

            # Get symbol info (needed for various checks)
            current_price = position['price_current']
            symbol_info = self.mt5.get_symbol_info(symbol)
            pip_value = symbol_info.get('point', 0.0001)

            # PARTIAL CLOSE: Apply to ALL profitable positions (original + grid + DCA)
            # This runs for ALL positions, not just tracked ones
            if self.partial_close_manager and position['profit'] > 0:
                # Track position if not already tracked
                if ticket not in self.partial_close_manager.partial_closes:
                    # Calculate TP price based on VWAP or other exit logic
                    # For now, use a reasonable default TP
                    entry_price = position['price_open']
                    pos_type = 'buy' if position['type'] == 0 else 'sell'

                    # Estimate TP price using default from config
                    tp_distance = DEFAULT_TP_PIPS * pip_value
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
                    logger.info(f"Partial close: {ticket} - {partial_action['close_percent']}% at {partial_action['level_percent']}% to TP")

                    # Check if close_volume equals or exceeds position volume (final close)
                    if close_volume >= position['volume']:
                        # Close entire position instead of partial
                        if self.mt5.close_position(ticket):
                            logger.info(f"Full close successful: {position['volume']} lots (final partial close)")
                            self.recovery_manager.untrack_position(ticket)
                            self.stats['trades_closed'] += 1
                    else:
                        # Close partial volume
                        if self.mt5.close_partial_position(ticket, close_volume):
                            logger.info(f"Partial close successful: {close_volume} lots")

            # RECOVERY & EXIT CONDITIONS: Only for tracked original positions
            if ticket in self.recovery_manager.tracked_positions:
                # Check recovery triggers
                recovery_actions = self.recovery_manager.check_all_recovery_triggers(
                    ticket, current_price, pip_value
                )

                # Execute recovery actions
                for action in recovery_actions:
                    self._execute_recovery_action(action)

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
                    # CRITICAL: Reassess market before closing - may need to close ALL reversion trades
                    self._reassess_market_on_stack_kill(symbol, ticket)
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
                    logger.info(f"Exit signal detected for {ticket} - VWAP reversion")
                    if self.mt5.close_position(ticket):
                        self.recovery_manager.untrack_position(ticket)
                        self.stats['trades_closed'] += 1

    def _analyze_market_regime(self, h1_data: pd.DataFrame) -> dict:
        """
        Analyze market regime once to avoid redundant calculations
        Used to route signals intelligently and avoid calculating ADX/Hurst twice

        Args:
            h1_data: H1 timeframe data

        Returns:
            Dict with regime analysis (ADX, Hurst, regime, confidence, etc.)
        """
        # Calculate ADX for trend strength
        data_with_adx = calculate_adx(h1_data.copy(), period=14)
        if len(data_with_adx) > 0:
            latest_adx = data_with_adx.iloc[-1]
            adx = latest_adx['adx']
            plus_di = latest_adx['plus_di']
            minus_di = latest_adx['minus_di']
        else:
            adx = 0
            plus_di = 0
            minus_di = 0

        # Calculate Hurst exponent for trend persistence
        hurst = calculate_hurst_exponent(h1_data['close'].tail(100))

        # Analyze candle direction
        candle_info = analyze_candle_direction(h1_data, lookback=5)

        # Combine ADX + Hurst for comprehensive regime detection
        market_analysis = combine_hurst_adx_analysis(hurst, adx, plus_di, minus_di)

        return {
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di,
            'hurst': hurst,
            'candle_alignment': candle_info['alignment'],
            'candle_aligned': candle_info['aligned'],
            'regime': market_analysis['regime'],
            'strategy': market_analysis['strategy'],
            'confidence': market_analysis['confidence'],
            'should_mean_revert': market_analysis['should_mean_revert'],
            'should_trend_follow': market_analysis['should_trend_follow'],
            'danger_zone': market_analysis['danger_zone']
        }

    def _check_for_signals(self, symbol: str):
        """
        Check for new entry signals with BIDIRECTIONAL regime-based routing

        RANGING → TRENDING: MR rejected → Try BO
        TRENDING → RANGING: BO rejected → Try MR
        """
        if symbol not in self.market_data_cache:
            if self.test_mode:
                logger.info(f"No market data cached for {symbol}")
            return

        # Check if symbol is blacklisted (due to trending market)
        if symbol in self.symbol_blacklist:
            blacklist_until = self.symbol_blacklist[symbol]
            if get_current_time() < blacklist_until:
                return  # Still blacklisted
            else:
                # Blacklist expired, remove it
                del self.symbol_blacklist[symbol]
                logger.info(f"{symbol} blacklist expired - resuming trading")

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

        # OPTIMIZATION: Analyze market regime ONCE (shared by both strategies)
        market_regime = self._analyze_market_regime(h1_data)

        if self.test_mode:
            logger.info(f"{symbol}: Regime={market_regime['regime']}, MR={can_trade_mr}, BO={can_trade_bo}")

        # BIDIRECTIONAL ROUTING: Prioritize based on regime, fallback to opposite strategy
        if market_regime['regime'] == 'ranging_confirmed':
            # RANGING → TRENDING: Try MR first (optimal), fallback to BO
            logger.debug(f"{symbol}: Ranging confirmed - MR priority, BO fallback")

            if can_trade_mr:
                signal = self.signal_detector.detect_signal(h1_data, d1_data, w1_data, symbol)
                if signal:
                    signal['strategy_type'] = 'mean_reversion'
                    signal['regime'] = market_regime['regime']

            # Fallback to breakout if MR found nothing
            if signal is None and can_trade_bo and self.breakout_strategy:
                signal = self._detect_breakout_signal(symbol, h1_data)

        elif market_regime['regime'] in ['trending_confirmed', 'strong_trending']:
            # TRENDING → RANGING: Try BO first (optimal), fallback to MR
            logger.debug(f"{symbol}: Trending confirmed - BO priority, MR fallback")

            if can_trade_bo and self.breakout_strategy:
                signal = self._detect_breakout_signal(symbol, h1_data)

            # Fallback to mean reversion if BO found nothing
            if signal is None and can_trade_mr:
                signal = self.signal_detector.detect_signal(h1_data, d1_data, w1_data, symbol)
                if signal:
                    signal['strategy_type'] = 'mean_reversion'
                    signal['regime'] = market_regime['regime']

        else:
            # UNCERTAIN REGIME: Try both (MR first by default)
            logger.debug(f"{symbol}: {market_regime['regime']} - trying both strategies")

            if can_trade_mr:
                signal = self.signal_detector.detect_signal(h1_data, d1_data, w1_data, symbol)
                if signal:
                    signal['strategy_type'] = 'mean_reversion'
                    signal['regime'] = market_regime['regime']

            if signal is None and can_trade_bo and self.breakout_strategy:
                signal = self._detect_breakout_signal(symbol, h1_data)

        if signal is None:
            if self.test_mode:
                logger.debug(f"No signal detected for {symbol} (regime: {market_regime['regime']})")
            return

        # Signal detected!
        self.stats['signals_detected'] += 1

        if self.test_mode:
            logger.info(f"SIGNAL DETECTED for {symbol}!")

        logger.info(f"Signal: {signal.get('strategy_type', 'unknown').upper()}")
        logger.info(self.signal_detector.get_signal_summary(signal))

        # Log signal to specialized logger
        logger.log_signal(signal)

        # Execute trade
        self._execute_signal(signal)

    def _detect_breakout_signal(self, symbol: str, h1_data: pd.DataFrame) -> Optional[Dict]:
        """
        Detect breakout signal (extracted for bidirectional routing)

        Args:
            symbol: Trading symbol
            h1_data: H1 timeframe data

        Returns:
            Signal dict or None
        """
        # DEBUG: Entry point logging
        if self.test_mode:
            logger.info(f"   Checking breakout signal for {symbol}...")

        # Get current price and volume
        latest_bar = h1_data.iloc[-1]
        current_price = latest_bar['close']

        # Get volume - handle both 'volume' and 'tick_volume' columns
        if 'volume' in latest_bar:
            current_volume = latest_bar['volume']
        elif 'tick_volume' in latest_bar:
            current_volume = latest_bar['tick_volume']
        else:
            current_volume = 0
            logger.warning(f"Warning: No volume data for {symbol}, using 0")

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
            return {
                'symbol': symbol,
                'direction': breakout_signal['direction'],
                'price': current_price,
                'strategy_type': 'breakout',
                'confluence_score': breakout_signal.get('score', 3),
                'factors': breakout_signal.get('factors', []),
                'confidence': breakout_signal.get('confidence', 'medium'),
                'regime': 'breakout_detected'
            }

        return None

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
            logger.error("Failed to get account/symbol info")
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
            logger.info(f"Breakout signal: Reducing lot size to {volume} (50% of base)")

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
            logger.warning(f"Trade validation failed: {reason}")
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
            logger.info(f"Trade opened: Ticket {ticket}")

            # Log trade to specialized logger
            logger.log_trade({
                'ticket': ticket,
                'symbol': symbol,
                'type': direction,
                'volume': volume,
                'price': price,
                'comment': comment
            })

            # Start tracking for recovery
            self.recovery_manager.track_position(
                ticket=ticket,
                symbol=symbol,
                entry_price=price,
                position_type=direction,
                volume=volume
            )

    def _reassess_market_on_stack_kill(self, symbol: str, failed_ticket: int):
        """
        Reassess market conditions after stack failure
        If market turned trending, close all reversion trades and blacklist symbol

        Args:
            symbol: Trading symbol
            failed_ticket: Ticket of failed stack
        """
        if symbol not in self.market_data_cache:
            logger.warning(f"Cannot reassess {symbol} - no market data cached")
            return

        h1_data = self.market_data_cache[symbol]['h1']

        # Calculate ADX for trend strength
        data_with_adx = calculate_adx(h1_data.copy(), period=14)
        latest_adx = data_with_adx.iloc[-1]
        adx = latest_adx['adx']
        plus_di = latest_adx['plus_di']
        minus_di = latest_adx['minus_di']

        # Calculate Hurst exponent for trend persistence
        hurst = calculate_hurst_exponent(h1_data['close'].tail(100))

        # Analyze candle direction
        candle_info = analyze_candle_direction(h1_data, lookback=5)

        # Combine Hurst + ADX analysis
        market_analysis = combine_hurst_adx_analysis(hurst, adx, plus_di, minus_di)

        # Log market state
        logger.warning(f"MARKET REASSESSMENT: {symbol} (after stack #{failed_ticket} killed)")
        logger.warning(f"   ADX: {adx:.1f} | Hurst: {hurst:.3f}")
        logger.warning(f"   Regime: {market_analysis['regime']}")
        logger.warning(f"   Candles: {candle_info['alignment']}")
        logger.warning(f"   Recommendation: {market_analysis['strategy']}")

        # CRITICAL: Check if market is now trending (dangerous for mean reversion)
        is_trending = (adx > 30 and candle_info['aligned']) or market_analysis['danger_zone']

        if is_trending:
            logger.critical(f"MARKET REGIME CHANGE DETECTED: {symbol}")
            logger.critical(f"   Market is TRENDING - Mean reversion UNSAFE!")
            logger.critical(f"   ADX: {adx:.1f} (TRENDING)")
            logger.critical(f"   Hurst: {hurst:.3f} ({market_analysis['hurst_behavior']})")
            logger.critical(f"   Candles: {candle_info['alignment']}")
            logger.critical(f"   Closing ALL reversion trades for {symbol}")

            # Close all reversion trades for this symbol
            positions = self.mt5.get_positions()
            closed_count = 0

            for pos in positions:
                # Only close reversion trades (Confluence comment), not breakout trades
                if pos['symbol'] == symbol and 'Confluence' in pos.get('comment', ''):
                    ticket = pos['ticket']
                    if self.mt5.close_position(ticket):
                        logger.info(f"   Closed reversion trade #{ticket}")
                        # Untrack if it's a tracked position
                        if ticket in self.recovery_manager.tracked_positions:
                            self.recovery_manager.untrack_position(ticket)
                        self.stats['trades_closed'] += 1
                        closed_count += 1
                    else:
                        logger.error(f"   Failed to close #{ticket}")

            logger.critical(f"   Total closed: {closed_count} reversion trades")

            # Blacklist symbol for 30 minutes
            blacklist_until = get_current_time() + timedelta(minutes=30)
            self.symbol_blacklist[symbol] = blacklist_until
            logger.warning(f"   {symbol} blacklisted until {blacklist_until.strftime('%H:%M:%S')}")

        else:
            logger.info(f"Market regime acceptable for {symbol}")
            logger.info(f"   Continuing normal operations")

    def _close_recovery_stack(self, original_ticket: int):
        """
        Close entire recovery stack (original + grid + hedge + DCA)

        Args:
            original_ticket: Original position ticket
        """
        # Get all tickets in the stack
        stack_tickets = self.recovery_manager.get_all_stack_tickets(original_ticket)

        logger.info(f"Closing recovery stack for {original_ticket}")
        logger.info(f"   Closing {len(stack_tickets)} positions...")

        closed_count = 0
        for ticket in stack_tickets:
            if self.mt5.close_position(ticket):
                closed_count += 1
                self.stats['trades_closed'] += 1
                logger.info(f"   Closed #{ticket}")
            else:
                logger.error(f"   Failed to close #{ticket}")

        # Untrack the original position
        self.recovery_manager.untrack_position(original_ticket)

        logger.info(f"Stack closed: {closed_count}/{len(stack_tickets)} positions")

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
        logger.info("=" * 60)
        logger.info("RELOADING CONFIGURATION")
        logger.info("=" * 60)
        success = reload_config()
        if success:
            print_current_config()
            logger.info("Config reloaded successfully!")
            logger.info("   Changes will take effect on next trading cycle")
        else:
            logger.error("Config reload failed")
        logger.info("=" * 60)
        return success
