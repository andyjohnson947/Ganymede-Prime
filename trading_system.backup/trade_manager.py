"""
Main Trade Manager
Orchestrates all trading activities based on EA reverse engineering
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Callable
import logging

import trading_config as config
from confluence_analyzer import ConfluenceAnalyzer
from position_managers import Position, GridManager, HedgeManager, RecoveryManager
from risk_manager import RiskManager


class TradeManager:
    """Main trading system orchestrator"""

    def __init__(self, symbols: Optional[List[str]] = None,
                 timeframe: str = 'M15',
                 initial_balance: float = config.INITIAL_BALANCE,
                 log_callback: Optional[Callable[[str, str], None]] = None):
        """
        Initialize Trade Manager

        Args:
            symbols: List of trading symbols (uses first symbol for now)
            timeframe: Trading timeframe (M15, H1, etc.)
            initial_balance: Initial account balance
            log_callback: Optional callback function(message, level) for GUI logging
        """
        self.symbols = symbols or [config.DEFAULT_SYMBOL]
        self.symbol = self.symbols[0]  # Use first symbol for now
        self.timeframe = timeframe
        self.positions: List[Position] = []
        self.position_counter = 0
        self.log_callback = log_callback

        # Trading statistics
        self.stats = {
            'trades_opened': 0,
            'trades_closed': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl': 0.0,
            'today_trades': 0,
            'today_pnl': 0.0,
        }

        # Re-entry prevention
        self.last_entry_time = {}  # {symbol: datetime}
        self.last_entry_price = {}  # {symbol: price}
        self.entry_cooldown_minutes = 15  # Wait 15 min before re-entering same zone

        # Initialize managers
        self.confluence_analyzer = ConfluenceAnalyzer()
        self.grid_manager = GridManager()
        self.hedge_manager = HedgeManager()
        self.recovery_manager = RecoveryManager()
        self.risk_manager = RiskManager(initial_balance)

        # MT5 connection status
        self.mt5_connected = False

        # Logging
        self.setup_logging()

    def setup_logging(self):
        """Setup logging with UTF-8 encoding for Windows compatibility"""
        # Create file handler with UTF-8 encoding
        file_handler = logging.FileHandler('trading_system.log', encoding='utf-8')
        file_handler.setLevel(getattr(logging, config.LOG_LEVEL))

        # Create console handler with UTF-8 encoding
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, config.LOG_LEVEL))

        # Set encoding to UTF-8 for Windows console
        try:
            import sys
            if sys.stdout.encoding != 'utf-8':
                import io
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        except:
            pass  # If we can't change encoding, continue anyway

        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Setup logger
        self.logger = logging.getLogger('TradeManager')
        self.logger.setLevel(getattr(logging, config.LOG_LEVEL))
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def log(self, message: str, level: str = "info"):
        """
        Log message using callback (for GUI) or logger

        Args:
            message: Log message
            level: 'info', 'warning', 'error', 'success'
        """
        # Call GUI callback if available (always works with Unicode)
        if self.log_callback:
            self.log_callback(message, level)

        # Also log to file (with error handling for encoding issues)
        try:
            if level == 'error':
                self.logger.error(message)
            elif level == 'warning':
                self.logger.warning(message)
            else:
                self.logger.info(message)
        except UnicodeEncodeError:
            # Fallback: strip emojis and special characters if encoding fails
            ascii_message = message.encode('ascii', 'ignore').decode('ascii')
            if level == 'error':
                self.logger.error(ascii_message)
            elif level == 'warning':
                self.logger.warning(ascii_message)
            else:
                self.logger.info(ascii_message)

    def connect_mt5(self, login: int, password: str, server: str) -> bool:
        """Connect to MT5"""
        # Check if already connected
        if self.mt5_connected:
            self.log("MT5 already connected", "info")
            return True

        # Ensure clean state - shutdown any existing connection
        try:
            mt5.shutdown()
        except:
            pass

        # Initialize MT5 connection
        if not mt5.initialize():
            error = mt5.last_error()
            self.log(f"MT5 initialization failed: {error}", "error")
            self.log("Make sure MetaTrader 5 terminal is installed and running", "error")
            return False

        # Login to trading account
        if not mt5.login(login, password, server):
            error = mt5.last_error()
            self.log(f"MT5 login failed: {error}", "error")
            self.log(f"Check credentials: Login={login}, Server={server}", "error")
            mt5.shutdown()  # Clean up on failed login
            return False

        # Verify connection
        account_info = mt5.account_info()
        if account_info is None:
            self.log("Failed to get account info after login", "error")
            mt5.shutdown()
            return False

        self.mt5_connected = True
        self.log(f"Connected to MT5: {server}", "success")
        self.log(f"Account: {account_info.login} | Balance: ${account_info.balance:.2f}", "info")
        return True

    def disconnect_mt5(self):
        """Disconnect from MT5"""
        if self.mt5_connected:
            mt5.shutdown()
            self.mt5_connected = False
            self.log("Disconnected from MT5", "info")

    def get_filling_mode(self, symbol: str):
        """
        Get the appropriate filling mode for the symbol

        Different brokers support different filling modes:
        - FOK (Fill or Kill): All or nothing
        - IOC (Immediate or Cancel): Partial fills allowed
        - RETURN: For pending orders
        """
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return mt5.ORDER_FILLING_FOK  # Default fallback

        # Check which filling modes are supported
        filling = symbol_info.filling_mode

        # Prefer IOC for immediate execution (most commonly supported)
        if filling & 0x02:  # IOC supported
            return mt5.ORDER_FILLING_IOC
        elif filling & 0x01:  # FOK supported
            return mt5.ORDER_FILLING_FOK
        else:  # RETURN supported
            return mt5.ORDER_FILLING_RETURN

    def get_market_data(self, timeframe=mt5.TIMEFRAME_H1, bars=200) -> pd.DataFrame:
        """Fetch market data from MT5"""
        if not self.mt5_connected:
            self.logger.error("Not connected to MT5")
            return pd.DataFrame()

        rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, bars)

        if rates is None or len(rates) == 0:
            self.logger.error(f"Failed to get market data: {mt5.last_error()}")
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)

        # Calculate VWAP
        df['VWAP'] = (df['close'] * df['tick_volume']).cumsum() / df['tick_volume'].cumsum()

        return df

    def execute_order(self, order_type: str, lot_size: float,
                     level_type: str = 'initial', level_number: int = 0,
                     hedge_pair_id: Optional[int] = None) -> Optional[Position]:
        """
        Execute market order via MT5

        Args:
            order_type: 'buy' or 'sell'
            lot_size: Position size
            level_type: 'initial', 'grid', 'hedge', 'recovery'
            level_number: Level number for tracking
            hedge_pair_id: ID linking hedge to original positions

        Returns:
            Position object or None if failed
        """
        if not self.mt5_connected:
            self.logger.error("Cannot execute order - not connected to MT5")
            return None

        # Get current price
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            self.logger.error(f"Failed to get tick data: {mt5.last_error()}")
            return None

        # Prepare request
        point = mt5.symbol_info(self.symbol).point
        price = tick.ask if order_type == 'buy' else tick.bid
        filling_mode = self.get_filling_mode(self.symbol)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": lot_size,
            "type": mt5.ORDER_TYPE_BUY if order_type == 'buy' else mt5.ORDER_TYPE_SELL,
            "price": price,
            "deviation": int(config.MAX_SLIPPAGE_PIPS),
            "magic": 234000,
            "comment": f"GTC25-{level_type}-L{level_number}"[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }

        # Send order
        result = mt5.order_send(request)

        if result is None:
            self.logger.error(f"Order send failed: {mt5.last_error()}")
            return None

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(f"Order failed: {result.comment}")
            return None

        # Create position object
        position = Position(
            ticket=result.order,
            symbol=self.symbol,
            position_type=order_type,
            entry_price=result.price,
            lot_size=lot_size,
            entry_time=datetime.now(),
            level_type=level_type,
            level_number=level_number,
            hedge_pair_id=hedge_pair_id
        )

        self.positions.append(position)
        self.position_counter += 1

        # Update statistics
        self.stats['trades_opened'] += 1
        self.stats['today_trades'] += 1

        pair_info = f" [Pair#{hedge_pair_id}]" if hedge_pair_id else ""
        self.log(f"Opened {order_type.upper()} {lot_size} @ {result.price} ({level_type} L{level_number}){pair_info}", "success")

        return position

    def close_position(self, position: Position) -> bool:
        """Close a specific position"""
        if not self.mt5_connected or not position.is_open:
            return False

        # Get current price for the position's symbol (not just self.symbol)
        tick = mt5.symbol_info_tick(position.symbol)
        if tick is None:
            self.log(f"[ERROR] Failed to get tick for {position.symbol}", "error")
            return False

        price = tick.bid if position.type == 'buy' else tick.ask
        filling_mode = self.get_filling_mode(position.symbol)

        # Prepare close request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": position.lot_size,
            "type": mt5.ORDER_TYPE_SELL if position.type == 'buy' else mt5.ORDER_TYPE_BUY,
            "position": position.ticket,
            "price": price,
            "deviation": int(config.MAX_SLIPPAGE_PIPS),
            "magic": 234000,
            "comment": "GTC25-close"[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(f"Failed to close position {position.ticket}")
            return False

        # Calculate profit
        profit_pips = position.get_pips_profit(price)
        profit_usd = profit_pips * position.lot_size * 10  # Rough calculation

        position.close(price, datetime.now(), profit_usd)

        # Update statistics
        self.stats['trades_closed'] += 1
        self.stats['total_pnl'] += profit_usd
        self.stats['today_pnl'] += profit_usd
        if profit_usd > 0:
            self.stats['wins'] += 1
        else:
            self.stats['losses'] += 1

        log_level = "success" if profit_usd > 0 else "warning"
        self.log(f"Closed {position.type.upper()} {position.lot_size} @ {price} | P/L: ${profit_usd:.2f}", log_level)

        # Update risk manager
        self.risk_manager.record_trade_result(profit_usd)

        return True

    def check_entry_signal(self, current_data: pd.DataFrame) -> Optional[Dict]:
        """
        Check for entry signals using confluence analysis

        Returns:
            Signal dict or None
        """
        if current_data.empty:
            return None

        current_price = current_data['close'].iloc[-1]

        # Analyze confluence
        signal = self.confluence_analyzer.analyze_confluence(current_price, current_data)

        if signal['should_trade']:
            self.log(f"Entry Signal: {signal['direction'].upper()} | "
                    f"Score: {signal['confluence_score']} | "
                    f"Factors: {', '.join(signal['factors'])}", "info")

        return signal if signal['should_trade'] else None

    def _check_entry_cooldown(self, current_price: float, current_time: datetime) -> Tuple[bool, str]:
        """
        Check if enough time has passed since last entry to prevent re-entry loop

        Returns:
            (can_enter, reason_if_not)
        """
        # Check if we have a recent entry
        if self.symbol not in self.last_entry_time:
            return True, ""  # No previous entry, OK to enter

        last_time = self.last_entry_time[self.symbol]
        last_price = self.last_entry_price.get(self.symbol, 0)

        # Calculate time since last entry
        time_elapsed = (current_time - last_time).total_seconds() / 60  # minutes

        # Check cooldown period
        if time_elapsed < self.entry_cooldown_minutes:
            # Check if price has moved significantly (>50 pips away)
            price_diff_pips = abs(current_price - last_price) / config.POINT_VALUE

            if price_diff_pips < 50:
                # Too soon and price too close - block entry
                remaining = self.entry_cooldown_minutes - time_elapsed
                return False, f"Cooldown active ({remaining:.1f} min remaining, price only {price_diff_pips:.0f} pips from last entry)"
            else:
                # Price moved far enough, allow entry despite cooldown
                return True, ""

        # Enough time has passed
        return True, ""

    def sync_positions_from_mt5(self):
        """Sync internal position tracking with live MT5 positions"""
        if not self.mt5_connected:
            return

        import re

        # Get ALL positions for this symbol (not just first symbol in list)
        mt5_positions = mt5.positions_get(symbol=self.symbol)
        if not mt5_positions:
            return

        # Get tickets we're already tracking (both open and closed)
        all_tracked_tickets = {p.ticket for p in self.positions}

        # Add any MT5 positions we're not tracking
        synced_count = 0
        for mt5_pos in mt5_positions:
            if mt5_pos.ticket not in all_tracked_tickets:
                # Validate this is our EA's position (check magic number or comment)
                if not (mt5_pos.magic == 234000 or 'GTC25' in mt5_pos.comment):
                    continue  # Skip positions from other EAs

                # Found orphaned position - add to tracking
                pos_type = 'buy' if mt5_pos.type == 0 else 'sell'

                # Parse level info from comment if available
                level_type = 'initial'
                level_number = 0
                if 'grid' in mt5_pos.comment.lower():
                    level_type = 'grid'
                    match = re.search(r'L(\d+)', mt5_pos.comment)
                    if match:
                        level_number = int(match.group(1))
                elif 'hedge' in mt5_pos.comment.lower():
                    level_type = 'hedge'
                elif 'recovery' in mt5_pos.comment.lower():
                    level_type = 'recovery'
                    match = re.search(r'L(\d+)', mt5_pos.comment)
                    if match:
                        level_number = int(match.group(1))

                position = Position(
                    ticket=mt5_pos.ticket,
                    symbol=mt5_pos.symbol,
                    position_type=pos_type,
                    entry_price=mt5_pos.price_open,
                    lot_size=mt5_pos.volume,
                    entry_time=datetime.fromtimestamp(mt5_pos.time),
                    level_type=level_type,
                    level_number=level_number
                )
                self.positions.append(position)
                synced_count += 1

        if synced_count > 0:
            self.log(f"[SYNC] Found {synced_count} orphaned positions - now managing them", "warning")

    def manage_positions(self):
        """
        Manage existing positions (grid, hedge, recovery)

        This is called every tick/bar to check if we should:
        - Add grid levels
        - Open hedge
        - Start recovery
        - Close positions
        """
        # First sync with MT5 to catch any orphaned positions
        self.sync_positions_from_mt5()

        open_positions = [p for p in self.positions if p.is_open]

        if not open_positions:
            return

        # Get LIVE tick price for accurate P&L
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            self.logger.error("Failed to get tick for position management")
            return

        # Group positions by direction
        buy_positions = [p for p in open_positions if p.type == 'buy']
        sell_positions = [p for p in open_positions if p.type == 'sell']

        # Manage buy positions (use bid price - what we'd get if we close)
        if buy_positions:
            self._manage_direction_positions(buy_positions, tick.bid, 'buy')

        # Manage sell positions (use ask price - what we'd pay to close)
        if sell_positions:
            self._manage_direction_positions(sell_positions, tick.ask, 'sell')

        # Manage hedge pairs using net P&L logic (ORIGINAL EA BEHAVIOR)
        self._manage_hedge_pairs(open_positions, tick)

    def _manage_hedge_pairs(self, all_positions: List[Position], tick):
        """
        Manage hedge pairs using net P&L logic (matches original blackbox EA)

        Implements two exit strategies:
        1. Close both when net P&L > 0
        2. Advanced: Close losing hedge when original is profitable
        """
        hedge_pairs = self.hedge_manager.get_hedge_pairs(all_positions)

        for pair_id, pair_data in hedge_pairs.items():
            original_positions = pair_data['original']
            hedge_positions = pair_data['hedge']

            if not original_positions or not hedge_positions:
                continue

            # Determine correct price for each direction
            original_direction = original_positions[0].type
            if original_direction == 'buy':
                original_price = tick.bid  # BUY closes at bid
                hedge_price = tick.ask     # SELL (hedge) closes at ask
            else:
                original_price = tick.ask  # SELL closes at ask
                hedge_price = tick.bid     # BUY (hedge) closes at bid

            # Calculate weighted price for net P&L
            # Use appropriate price for each position type
            weighted_price = original_price  # Simplified - uses original direction price

            # Check exit conditions using advanced logic
            close_both, close_hedge_only, reason = self.hedge_manager.should_close_hedge_pair(
                original_positions, hedge_positions, weighted_price, use_advanced_exit=True
            )

            if close_both:
                # Close entire pair (net profitable)
                net_pnl, orig_pnl, hedge_pnl = self.hedge_manager.calculate_pair_net_pnl(
                    original_positions, hedge_positions, weighted_price
                )

                self.log(f"[HEDGE PAIR #{pair_id}] {reason}", "success")
                self.log(f"  Original: {orig_pnl:+.1f} pips | Hedge: {hedge_pnl:+.1f} pips | NET: {net_pnl:+.1f} pips", "success")

                # Close all positions in the pair
                for pos in original_positions + hedge_positions:
                    self.close_position(pos)

            elif close_hedge_only:
                # Advanced logic: Close losing hedge, keep profitable original
                net_pnl, orig_pnl, hedge_pnl = self.hedge_manager.calculate_pair_net_pnl(
                    original_positions, hedge_positions, weighted_price
                )

                self.log(f"[HEDGE PAIR #{pair_id}] {reason}", "info")
                self.log(f"  Original: {orig_pnl:+.1f} pips (keeping) | Hedge: {hedge_pnl:+.1f} pips (closing)", "info")

                # Close only the hedge positions
                for pos in hedge_positions:
                    self.close_position(pos)

                # Unpair original positions so they can be managed independently
                for pos in original_positions:
                    pos.hedge_pair_id = None

    def _manage_direction_positions(self, positions: List[Position],
                                   current_price: float, direction: str):
        """Manage positions for a specific direction"""
        # Check if we should add grid level
        if self.grid_manager.should_open_grid_level(positions, current_price, direction):
            grid_level = len([p for p in positions if p.level_type in ['initial', 'grid']])
            lot_size = self.grid_manager.get_grid_lot_size(grid_level)

            self.log(f"[GRID] Opening grid level {grid_level} for {direction.upper()}", "info")
            self.execute_order(direction, lot_size, 'grid', grid_level)

        # Check if we should open hedge
        should_hedge, hedge_direction, hedge_lot_size, hedge_pair_id = self.hedge_manager.should_open_hedge(
            positions, current_price
        )

        if should_hedge:
            self.log(f"[HEDGE] Opening HEDGE: {hedge_direction.upper()} {hedge_lot_size} "
                    f"(2.4x ratio - Pair #{hedge_pair_id})", "warning")
            self.execute_order(hedge_direction, hedge_lot_size, 'hedge', 0, hedge_pair_id=hedge_pair_id)

        # Check if we should start/continue recovery
        should_recover, recovery_lot_size = self.recovery_manager.should_open_recovery_level(
            positions, current_price, direction
        )

        if should_recover:
            recovery_level = len([p for p in positions if p.level_type == 'recovery']) + 1
            self.log(f"[RECOVERY] Opening RECOVERY level {recovery_level} for {direction.upper()} "
                    f"({recovery_lot_size} lots) - Martingale active", "warning")
            self.execute_order(direction, recovery_lot_size, 'recovery', recovery_level)

        # Check if we should close all positions (breakeven or profit)
        # Only for positions NOT in a hedge pair
        unpaired_positions = [p for p in positions if p.hedge_pair_id is None]
        if unpaired_positions:
            self._check_exit_conditions(unpaired_positions, current_price, direction)

    def _check_exit_conditions(self, positions: List[Position],
                               current_price: float, direction: str):
        """Check if we should exit positions"""
        # Calculate total P&L
        total_pnl_pips = sum(p.get_pips_profit(current_price) * p.lot_size
                            for p in positions)

        # Close all if profitable (breakeven or better)
        if total_pnl_pips > 0:
            avg_entry = self.grid_manager.calculate_average_entry(positions)

            self.log(f"[PROFIT] Closing all {direction.upper()} positions at profit "
                    f"(Total: {total_pnl_pips:.1f} pips) - Strategy successful!", "success")

            for position in positions:
                self.close_position(position)

    def _print_cycle_summary(self, current_data: pd.DataFrame, signal: Optional[Dict]):
        """Print detailed cycle summary for user feedback"""
        current_price = current_data['close'].iloc[-1]
        open_positions = [p for p in self.positions if p.is_open]

        self.log("=" * 60, "info")
        self.log(f"CYCLE SUMMARY - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "info")
        self.log("=" * 60, "info")

        # Market conditions
        vwap = current_data['VWAP'].iloc[-1]
        std = current_data['close'].rolling(20).std().iloc[-1]
        deviation = abs(current_price - vwap) / std if std > 0 else 0

        self.log(f"Current Price: {current_price:.5f} | VWAP: {vwap:.5f}", "info")
        self.log(f"Deviation: {deviation:.2f} SD from VWAP", "info")

        # Initialize position counts (default to 0)
        grid_count = 0
        hedge_count = 0
        recovery_count = 0

        # Position status
        if open_positions:
            self.log(f"\nActive Positions: {len(open_positions)}", "info")

            # Count by type
            grid_count = len([p for p in open_positions if p.level_type in ['initial', 'grid']])
            hedge_count = len([p for p in open_positions if p.level_type == 'hedge'])
            recovery_count = len([p for p in open_positions if p.level_type == 'recovery'])

            self.log(f"  Grid: {grid_count} | Hedge: {hedge_count} | Recovery: {recovery_count}", "info")

            # Total P&L - use LIVE tick price for accuracy!
            tick = mt5.symbol_info_tick(self.symbol)
            if tick:
                # Group by direction and use correct close price
                buy_positions = [p for p in open_positions if p.type == 'buy']
                sell_positions = [p for p in open_positions if p.type == 'sell']

                # BUY positions close at BID, SELL positions close at ASK
                total_pnl = 0
                for p in buy_positions:
                    total_pnl += p.get_pips_profit(tick.bid) * p.lot_size
                for p in sell_positions:
                    total_pnl += p.get_pips_profit(tick.ask) * p.lot_size

                self.log(f"  Current P&L: {total_pnl:.1f} pips (LIVE tick price)", "info")
            else:
                # Fallback to H1 bar if tick unavailable
                total_pnl = sum(p.get_pips_profit(current_price) * p.lot_size for p in open_positions)
                self.log(f"  Current P&L: {total_pnl:.1f} pips (H1 bar estimate)", "warning")

            # Strategy phase
            if recovery_count > 0:
                self.log(f"  [!] RECOVERY PHASE (Level {recovery_count}/5)", "warning")
                self.log(f"  Strategy Status: Martingale active - position averaging", "warning")
            elif hedge_count > 0:
                self.log(f"  [HEDGE] HEDGE PHASE (2.4x overhedge active)", "warning")
                self.log(f"  Strategy Status: Hedged - waiting for reversal or continuation", "info")
            elif grid_count > 1:
                self.log(f"  [GRID] GRID PHASE (Level {grid_count}/6)", "info")
                self.log(f"  Strategy Status: Building grid - averaging down", "info")
            else:
                self.log(f"  INITIAL ENTRY", "info")
                self.log(f"  Strategy Status: Monitoring for grid triggers", "info")
        else:
            self.log(f"No Open Positions - Scanning for entry signals", "info")

        # Confluence analysis
        if signal:
            self.log(f"\n[SIGNAL] Signal Detected:", "success")
            self.log(f"  Direction: {signal['direction'].upper()}", "success")
            self.log(f"  Confluence Score: {signal['confluence_score']}/8", "success")
            self.log(f"  Active Factors: {', '.join(signal['factors'])}", "success")
        else:
            self.log(f"\nNo Entry Signal (waiting for 4+ confluence)", "info")

        # Statistics
        stats = self.get_statistics()
        self.log(f"\nSession Statistics:", "info")
        self.log(f"  Total Trades: {stats['today_trades']} | Win Rate: {stats['win_rate']:.1f}%", "info")
        self.log(f"  Today's P&L: ${stats['today_pnl']:.2f} | Total P&L: ${stats['total_pnl']:.2f}", "info")
        self.log(f"  Current Drawdown: {stats['drawdown']:.1f}%", "info")

        # Strategy adherence check
        self.log(f"\nStrategy Adherence Check:", "info")
        if grid_count > config.MAX_GRID_LEVELS:
            self.log(f"  [!] WARNING: Grid levels ({grid_count}) exceed max ({config.MAX_GRID_LEVELS})", "warning")
        if recovery_count > config.MAX_RECOVERY_LEVELS:
            self.log(f"  [!] WARNING: Recovery levels ({recovery_count}) exceed max ({config.MAX_RECOVERY_LEVELS})", "error")
        if stats['drawdown'] > config.MAX_DRAWDOWN_PCT * 0.8:
            self.log(f"  [!] WARNING: Approaching max drawdown limit ({config.MAX_DRAWDOWN_PCT}%)", "warning")

        if grid_count <= config.MAX_GRID_LEVELS and recovery_count <= config.MAX_RECOVERY_LEVELS:
            self.log(f"  All parameters within configured limits", "success")

        self.log("=" * 60 + "\n", "info")

    def run_trading_cycle(self):
        """
        Main trading cycle - call this periodically (e.g., every bar/minute)
        """
        if not self.mt5_connected:
            self.log("Not connected to MT5", "error")
            return

        # Get current market data
        current_data = self.get_market_data()

        if current_data.empty:
            return

        current_price = current_data['close'].iloc[-1]
        current_time = datetime.now()

        # Update previous day levels (once per day)
        self.confluence_analyzer.calculate_previous_day_levels(current_data)

        # Check risk controls
        can_trade, reason = self.risk_manager.can_trade(
            self.positions, self.symbol, current_time
        )

        if not can_trade:
            self.log(f"[!] Trading disabled: {reason}", "warning")
            return

        # Manage existing positions
        self.manage_positions()

        # Check for new entry signals (only if no open positions)
        open_positions = [p for p in self.positions if p.is_open]
        signal = None

        if not open_positions:
            signal = self.check_entry_signal(current_data)

            if signal:
                # Check cooldown - prevent immediate re-entry
                current_price = current_data['close'].iloc[-1]
                can_enter, cooldown_reason = self._check_entry_cooldown(current_price, current_time)

                if not can_enter:
                    self.log(f"[COOLDOWN] Entry blocked: {cooldown_reason}", "warning")
                    signal = None  # Don't show signal if blocked by cooldown
                else:
                    # Execute initial entry
                    self.log(f"[SIGNAL] NEW ENTRY SIGNAL: {signal['direction'].upper()} | "
                            f"Confluence: {signal['confluence_score']}", "success")

                    self.execute_order(
                        signal['direction'],
                        config.GRID_BASE_LOT_SIZE,
                        'initial',
                        0
                    )

                    # Record entry for cooldown tracking
                    self.last_entry_time[self.symbol] = current_time
                    self.last_entry_price[self.symbol] = current_price

        # Print detailed cycle summary
        self._print_cycle_summary(current_data, signal)

    def get_status(self) -> Dict:
        """Get current trading status"""
        open_positions = [p for p in self.positions if p.is_open]

        return {
            'mt5_connected': self.mt5_connected,
            'symbol': self.symbol,
            'open_positions': len(open_positions),
            'total_positions': len(self.positions),
            'risk_status': self.risk_manager.get_risk_status(),
            'positions': [str(p) for p in open_positions],
        }

    def get_statistics(self) -> Dict:
        """
        Get trading statistics for GUI display

        Returns:
            Dictionary with current trading statistics
        """
        open_positions = [p for p in self.positions if p.is_open]

        # Calculate win rate
        total_closed = self.stats['wins'] + self.stats['losses']
        win_rate = (self.stats['wins'] / total_closed * 100) if total_closed > 0 else 0.0

        # Get current drawdown from risk manager
        risk_status = self.risk_manager.get_risk_status()
        drawdown = risk_status.get('current_drawdown_pct', 0.0)

        return {
            'open_positions': len(open_positions),
            'total_pnl': self.stats['total_pnl'],
            'win_rate': win_rate,
            'drawdown': drawdown,
            'today_trades': self.stats['today_trades'],
            'wins': self.stats['wins'],
            'losses': self.stats['losses'],
            'today_pnl': self.stats['today_pnl'],
        }

    def print_status(self):
        """Print status to console"""
        status = self.get_status()

        print("\n" + "=" * 80)
        print("TRADE MANAGER STATUS")
        print("=" * 80)
        print(f"Symbol: {status['symbol']}")
        print(f"MT5 Connected: {'[OK]' if status['mt5_connected'] else '[FAIL]'}")
        print(f"Open Positions: {status['open_positions']}")
        print(f"\nRisk Status:")
        for key, value in status['risk_status'].items():
            print(f"  {key}: {value}")

        if status['positions']:
            print(f"\nOpen Positions:")
            for pos in status['positions']:
                print(f"  {pos}")
        print("=" * 80)
