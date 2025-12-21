#!/usr/bin/env python3
"""
GUI Trading Application
Professional front-end for the EA trading system with parameter management
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
from pathlib import Path
from datetime import datetime
import threading
import queue
from typing import Dict, Any, Optional, List
import sys

# Try to import matplotlib for charts
try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("[WARNING] matplotlib not available - charts will be disabled")

# Try to import MetaTrader5 for backtesting
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    print("[WARNING] MetaTrader5 not available - backtesting will be disabled")

# Import trading system components
# Support both direct script execution and module import
try:
    # Try relative import first (when imported as module)
    from .trade_manager import TradeManager
    from . import trading_config as config
except ImportError:
    # Fall back to absolute import (when run as script)
    from trade_manager import TradeManager
    import trading_config as config

# Import backtesting components
if MT5_AVAILABLE:
    try:
        # Try relative import first
        try:
            from .backtest_engine import BacktestEngine, BacktestResults
            from .backtest import BacktestDataLoader
        except ImportError:
            # Fall back to absolute import
            from backtest_engine import BacktestEngine, BacktestResults
            from backtest import BacktestDataLoader
        BACKTEST_AVAILABLE = True
    except ImportError:
        BACKTEST_AVAILABLE = False
        print("[WARNING] Backtest modules not available")
else:
    BACKTEST_AVAILABLE = False


class ConfigManager:
    """Handles loading and saving configuration to local file"""

    def __init__(self, config_file: str = "trading_config.json"):
        self.config_file = Path(config_file)
        self.default_config = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration from trading_config.py"""
        return {
            # Grid Parameters
            'grid_spacing_pips': config.GRID_SPACING_PIPS,
            'max_grid_levels': config.MAX_GRID_LEVELS,
            'grid_lot_size': config.GRID_BASE_LOT_SIZE,

            # Hedge Parameters
            'hedge_ratio': config.HEDGE_RATIO,
            'hedge_trigger_pips': config.HEDGE_TRIGGER_PIPS,

            # Recovery Parameters
            'martingale_multiplier': config.MARTINGALE_MULTIPLIER,
            'max_recovery_levels': config.MAX_RECOVERY_LEVELS,

            # Confluence Parameters
            'min_confluence_score': config.MIN_CONFLUENCE_SCORE,
            'confluence_tolerance_pct': config.CONFLUENCE_TOLERANCE_PCT,

            # Risk Parameters
            'max_drawdown_pct': config.MAX_DRAWDOWN_PCT,
            'daily_loss_limit_pct': config.MAX_DAILY_LOSS_PCT,
            'max_consecutive_losses': config.MAX_CONSECUTIVE_LOSSES,
            'max_positions_per_symbol': config.MAX_POSITIONS_PER_SYMBOL,

            # Trading Parameters
            'symbols': [config.DEFAULT_SYMBOL],
            'timeframe': 'M15',
            'update_interval_seconds': 60,

            # MT5 Credentials
            'mt5_login': '',
            'mt5_password': '',
            'mt5_server': '',
        }

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file or return defaults"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    saved_config = json.load(f)
                # Merge with defaults to ensure all keys exist
                config = self.default_config.copy()
                config.update(saved_config)
                return config
            except Exception as e:
                print(f"Error loading config: {e}")
                return self.default_config.copy()
        return self.default_config.copy()

    def save_config(self, config: Dict[str, Any]) -> bool:
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False


class TradingGUI:
    """Main GUI Application for Trading System"""

    def __init__(self, root):
        self.root = root
        self.root.title("Ganymede Trade City - GTC25v1.0")
        self.root.geometry("1200x800")

        # Configuration management
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()

        # Trading state
        self.trade_manager: Optional[TradeManager] = None
        self.trading_thread: Optional[threading.Thread] = None
        self.is_trading = False
        self.trading_lock = threading.Lock()  # Thread safety for is_trading flag
        self.log_queue = queue.Queue()

        # Backtesting state
        self.backtest_results: List[BacktestResults] = []
        self.backtest_thread: Optional[threading.Thread] = None
        self.is_backtesting = False

        # Debug state
        self.debug_queue = queue.Queue()
        self.debug_history = []  # Store last 1000 debug messages
        self.max_debug_history = 1000

        # Build UI
        self._create_ui()

        # Load saved configuration into UI
        self._load_config_to_ui()

        # Start log queue processor
        self._process_log_queue()

    def _create_ui(self):
        """Create the user interface"""
        # Create tabbed notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tab 1: Live Trading
        self.trading_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.trading_tab, text="  Live Trading  ")
        self._create_live_trading_tab(self.trading_tab)

        # Tab 2: Backtesting
        self.backtest_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.backtest_tab, text="  Backtesting  ")
        self._create_backtest_tab(self.backtest_tab)

        # Tab 3: Live Debug
        self.debug_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.debug_tab, text="  Live Debug  ")
        self._create_debug_tab(self.debug_tab)

    def _create_live_trading_tab(self, parent):
        """Create live trading tab content"""
        # Main container (same as before)
        main_container = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel - Parameters
        left_panel = ttk.Frame(main_container)
        main_container.add(left_panel, weight=1)

        # Right panel - Console and Stats
        right_panel = ttk.Frame(main_container)
        main_container.add(right_panel, weight=2)

        # Create left panel content
        self._create_parameters_panel(left_panel)

        # Create right panel content
        self._create_console_panel(right_panel)

    def _create_parameters_panel(self, parent):
        """Create parameters configuration panel"""
        # Title
        title = ttk.Label(parent, text="Trading Parameters", font=('Arial', 14, 'bold'))
        title.pack(pady=10)

        # Scrollable frame for parameters
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Store entry widgets
        self.entries = {}

        # MT5 Credentials Section
        self._create_section(scrollable_frame, "MT5 Connection", [
            ("MT5 Login", 'mt5_login', 'text'),
            ("MT5 Password", 'mt5_password', 'password'),
            ("MT5 Server", 'mt5_server', 'text'),
        ])

        # Grid Parameters Section
        self._create_section(scrollable_frame, "Grid Strategy", [
            ("Grid Spacing (pips)", 'grid_spacing_pips', 'float'),
            ("Max Grid Levels", 'max_grid_levels', 'int'),
            ("Grid Lot Size", 'grid_lot_size', 'float'),
        ])

        # Hedge Parameters Section
        self._create_section(scrollable_frame, "Hedge Strategy", [
            ("Hedge Ratio (x)", 'hedge_ratio', 'float'),
            ("Hedge Trigger (pips)", 'hedge_trigger_pips', 'int'),
        ])

        # Recovery Parameters Section
        self._create_section(scrollable_frame, "Recovery Strategy", [
            ("Martingale Multiplier", 'martingale_multiplier', 'float'),
            ("Max Recovery Levels", 'max_recovery_levels', 'int'),
        ])

        # Confluence Parameters Section
        self._create_section(scrollable_frame, "Confluence Filters", [
            ("Min Confluence Score", 'min_confluence_score', 'int'),
            ("Confluence Tolerance (%)", 'confluence_tolerance_pct', 'float'),
        ])

        # Risk Parameters Section
        self._create_section(scrollable_frame, "Risk Management", [
            ("Max Drawdown (%)", 'max_drawdown_pct', 'float'),
            ("Daily Loss Limit (%)", 'daily_loss_limit_pct', 'float'),
            ("Max Consecutive Losses", 'max_consecutive_losses', 'int'),
            ("Max Positions per Symbol", 'max_positions_per_symbol', 'int'),
        ])

        # Trading Parameters Section
        self._create_section(scrollable_frame, "Trading Settings", [
            ("Symbols (comma-separated)", 'symbols', 'text'),
            ("Update Interval (seconds)", 'update_interval_seconds', 'int'),
        ])

        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(pady=20, padx=10, fill=tk.X)

        ttk.Button(button_frame, text="Save Configuration",
                   command=self._save_configuration).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Load Configuration",
                   command=self._load_configuration).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Reset to Defaults",
                   command=self._reset_to_defaults).pack(side=tk.LEFT, padx=5)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _create_section(self, parent, title: str, fields: list):
        """Create a parameter section with fields"""
        section = ttk.LabelFrame(parent, text=title, padding=10)
        section.pack(pady=10, padx=10, fill=tk.X)

        for label_text, key, field_type in fields:
            row = ttk.Frame(section)
            row.pack(fill=tk.X, pady=3)

            label = ttk.Label(row, text=label_text, width=25, anchor='w')
            label.pack(side=tk.LEFT)

            if field_type == 'password':
                entry = ttk.Entry(row, show='*', width=30)
            else:
                entry = ttk.Entry(row, width=30)

            entry.pack(side=tk.LEFT, padx=5)
            self.entries[key] = (entry, field_type)

    def _create_console_panel(self, parent):
        """Create console and statistics panel"""
        # Top section - Statistics
        stats_frame = ttk.LabelFrame(parent, text="Live Statistics", padding=10)
        stats_frame.pack(fill=tk.X, padx=5, pady=5)

        # Stats grid
        self.stats_labels = {}
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X)

        stats_items = [
            ("Status", "status"),
            ("Open Positions", "positions"),
            ("Total P&L", "pnl"),
            ("Win Rate", "win_rate"),
            ("Drawdown", "drawdown"),
            ("Today's Trades", "today_trades"),
        ]

        for i, (label, key) in enumerate(stats_items):
            row = i // 3
            col = i % 3

            frame = ttk.Frame(stats_grid)
            frame.grid(row=row, column=col, padx=10, pady=5, sticky='w')

            ttk.Label(frame, text=f"{label}:", font=('Arial', 9, 'bold')).pack(side=tk.LEFT)
            value_label = ttk.Label(frame, text="--", font=('Arial', 9))
            value_label.pack(side=tk.LEFT, padx=5)
            self.stats_labels[key] = value_label

        # Control buttons
        control_frame = ttk.Frame(stats_frame)
        control_frame.pack(fill=tk.X, pady=10)

        self.start_button = ttk.Button(control_frame, text="Start Trading",
                                       command=self._start_trading, style='Success.TButton')
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(control_frame, text="Stop Trading",
                                      command=self._stop_trading, state=tk.DISABLED,
                                      style='Danger.TButton')
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Middle section - Console
        console_frame = ttk.LabelFrame(parent, text="Trading Console", padding=10)
        console_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Console text area with scrollbar
        self.console = scrolledtext.ScrolledText(console_frame, height=20,
                                                  bg='#1e1e1e', fg='#00ff00',
                                                  font=('Consolas', 9))
        self.console.pack(fill=tk.BOTH, expand=True)
        self.console.config(state=tk.DISABLED)

        # Console control buttons
        console_controls = ttk.Frame(console_frame)
        console_controls.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(console_controls, text="Clear Console",
                   command=self._clear_console).pack(side=tk.LEFT, padx=5)

        self.autoscroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(console_controls, text="Auto-scroll",
                        variable=self.autoscroll_var).pack(side=tk.LEFT, padx=5)

    def _load_config_to_ui(self):
        """Load saved configuration into UI fields"""
        for key, (entry, field_type) in self.entries.items():
            value = self.config.get(key, '')
            if isinstance(value, list):
                value = ', '.join(value)
            entry.delete(0, tk.END)
            entry.insert(0, str(value))

    def _save_configuration(self):
        """Save current UI values to configuration file"""
        try:
            # Read values from UI
            for key, (entry, field_type) in self.entries.items():
                value = entry.get()

                # Convert to appropriate type
                if field_type == 'int':
                    self.config[key] = int(value)
                elif field_type == 'float':
                    self.config[key] = float(value)
                elif key == 'symbols':
                    self.config[key] = [s.strip() for s in value.split(',')]
                else:
                    self.config[key] = value

            # Save to file
            if self.config_manager.save_config(self.config):
                self._log("Configuration saved successfully", "success")
                messagebox.showinfo("Success", "Configuration saved successfully!")
            else:
                self._log("[ERROR] Failed to save configuration", "error")
                messagebox.showerror("Error", "Failed to save configuration")
        except Exception as e:
            self._log(f"[ERROR] Error saving configuration: {e}", "error")
            messagebox.showerror("Error", f"Invalid configuration: {e}")

    def _load_configuration(self):
        """Reload configuration from file"""
        self.config = self.config_manager.load_config()
        self._load_config_to_ui()
        self._log("Configuration loaded from file", "success")
        messagebox.showinfo("Success", "Configuration loaded successfully!")

    def _reset_to_defaults(self):
        """Reset all parameters to default values"""
        if messagebox.askyesno("Confirm Reset",
                               "Reset all parameters to default values?"):
            self.config = self.config_manager._get_default_config()
            self._load_config_to_ui()
            self._log("Configuration reset to defaults", "info")

    def _start_trading(self):
        """Start the trading system"""
        # Check if already trading (thread-safe)
        with self.trading_lock:
            if self.is_trading:
                return

        try:
            # Save current configuration first
            self._save_configuration()

            # Validate MT5 credentials
            if not all([self.config.get('mt5_login'),
                       self.config.get('mt5_password'),
                       self.config.get('mt5_server')]):
                messagebox.showerror("Error", "Please configure MT5 credentials")
                return

            # Clean up old trade manager if exists
            if self.trade_manager:
                try:
                    self._log("Cleaning up previous connection...", "info")
                    self.trade_manager.disconnect_mt5()
                    # Give MT5 time to fully disconnect
                    import time
                    time.sleep(0.5)
                except:
                    pass
                self.trade_manager = None

            # Update UI
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)

            # Set trading flag (thread-safe)
            with self.trading_lock:
                self.is_trading = True

            # Update stats
            self._update_stat('status', '[RUNNING]')

            # Start trading in separate thread
            self.trading_thread = threading.Thread(target=self._trading_loop, daemon=True)
            self.trading_thread.start()

            self._log("=" * 60, "info")
            self._log("TRADING SYSTEM STARTED", "success")
            self._log("=" * 60, "info")
            self._add_debug_log(f"Trading started with {len(self.config['symbols'])} symbols: {', '.join(self.config['symbols'])}", "success")
            self._add_debug_log(f"Update interval: {self.config.get('update_interval_seconds', 60)}s", "debug")

        except Exception as e:
            self._log(f"[ERROR] Failed to start trading: {e}", "error")
            messagebox.showerror("Error", f"Failed to start trading: {e}")
            self._stop_trading()

    def _stop_trading(self):
        """Stop the trading system"""
        with self.trading_lock:
            if not self.is_trading:
                return
            self.is_trading = False

        # Update UI
        self._reset_ui_after_stop()

        self._log("=" * 60, "info")
        self._log("TRADING SYSTEM STOPPED", "warning")
        self._log("=" * 60, "info")
        self._add_debug_log("Trading system stopped by user", "warning")

    def _reset_ui_after_stop(self):
        """Reset UI buttons after trading stops (thread-safe)"""
        # Ensure this runs on the main thread
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self._update_stat('status', '[STOPPED]')

    def _trading_loop(self):
        """Main trading loop running in separate thread"""
        try:
            # Initialize trade manager
            self.trade_manager = TradeManager(
                symbols=self.config['symbols'],
                timeframe=self.config.get('timeframe', 'M15'),
                log_callback=self._log
            )

            # Connect to MT5
            self._log("Connecting to MT5...", "info")
            self._add_debug_log(f"Attempting MT5 connection to {self.config['mt5_server']}", "debug")
            if not self.trade_manager.connect_mt5(
                login=int(self.config['mt5_login']),
                password=self.config['mt5_password'],
                server=self.config['mt5_server']
            ):
                self._log("[ERROR] Failed to connect to MT5", "error")
                self._add_debug_log("MT5 connection failed - check credentials and server", "error")
                self.is_trading = False
                self.root.after(0, self._reset_ui_after_stop)
                return

            self._log("Connected to MT5 successfully", "success")
            self._add_debug_log(f"MT5 connected - Account: {self.config['mt5_login']}, Server: {self.config['mt5_server']}", "success")

            # Trading loop
            interval = self.config.get('update_interval_seconds', 60)
            reconnect_attempts = 0
            max_reconnect_attempts = 3

            while self.is_trading:
                try:
                    # Check MT5 connection
                    if not self.trade_manager.mt5_connected:
                        reconnect_attempts += 1
                        if reconnect_attempts <= max_reconnect_attempts:
                            self._log(f"[WARNING] MT5 disconnected. Reconnection attempt {reconnect_attempts}/{max_reconnect_attempts}...", "warning")
                            if self.trade_manager.connect_mt5(
                                login=int(self.config['mt5_login']),
                                password=self.config['mt5_password'],
                                server=self.config['mt5_server']
                            ):
                                self._log("[SUCCESS] Reconnected to MT5", "success")
                                reconnect_attempts = 0
                            else:
                                self._log(f"[ERROR] Reconnection failed", "error")
                                threading.Event().wait(10)
                                continue
                        else:
                            self._log(f"[ERROR] Max reconnection attempts reached. Stopping trading.", "error")
                            self.is_trading = False
                            break

                    # Run trading cycle
                    self.trade_manager.run_trading_cycle()
                    reconnect_attempts = 0  # Reset on successful cycle

                    # Update statistics
                    self._update_statistics()

                    # Update debug information
                    self._update_debug_info()

                    # Wait for next interval
                    for _ in range(interval):
                        if not self.is_trading:
                            break
                        threading.Event().wait(1)

                except Exception as e:
                    self._log(f"[ERROR] Error in trading cycle: {e}", "error")
                    import traceback
                    self._log(f"[DEBUG] {traceback.format_exc()}", "error")
                    threading.Event().wait(5)

            # Cleanup
            self._log("Closing all positions...", "info")
            if self.trade_manager:
                self.trade_manager.disconnect_mt5()

        except Exception as e:
            self._log(f"[ERROR] Fatal error in trading loop: {e}", "error")
        finally:
            self.is_trading = False
            # Reset UI buttons from main thread
            self.root.after(0, self._reset_ui_after_stop)

    def _update_statistics(self):
        """Update statistics display (thread-safe)"""
        if not self.trade_manager:
            return

        try:
            # Get statistics from trade manager
            stats = self.trade_manager.get_statistics()

            # Schedule UI updates on main thread
            self.root.after(0, self._update_stat, 'positions', str(stats.get('open_positions', 0)))
            self.root.after(0, self._update_stat, 'pnl', f"${stats.get('total_pnl', 0.0):.2f}")
            self.root.after(0, self._update_stat, 'win_rate', f"{stats.get('win_rate', 0.0):.1f}%")
            self.root.after(0, self._update_stat, 'drawdown', f"{stats.get('drawdown', 0.0):.1f}%")
            self.root.after(0, self._update_stat, 'today_trades', str(stats.get('today_trades', 0)))

        except Exception as e:
            self._log(f"Error updating statistics: {e}", "error")

    def _update_stat(self, key: str, value: str):
        """Update a single statistic label"""
        if key in self.stats_labels:
            self.stats_labels[key].config(text=value)

    def _log(self, message: str, level: str = "info"):
        """Add message to console (thread-safe)"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put((timestamp, message, level))

        # Debug tab shows technical diagnostics only, not duplicate messages

    def _process_log_queue(self):
        """Process log messages from queue and update console"""
        try:
            while True:
                timestamp, message, level = self.log_queue.get_nowait()

                # Color coding
                color_map = {
                    'info': '#00ff00',
                    'success': '#00ff00',
                    'warning': '#ffaa00',
                    'error': '#ff0000',
                }
                color = color_map.get(level, '#00ff00')

                # Add to console
                self.console.config(state=tk.NORMAL)
                self.console.insert(tk.END, f"[{timestamp}] ", 'timestamp')
                self.console.insert(tk.END, f"{message}\n", level)

                # Apply color tags
                self.console.tag_config('timestamp', foreground='#888888')
                self.console.tag_config(level, foreground=color)

                # Auto-scroll if enabled
                if self.autoscroll_var.get():
                    self.console.see(tk.END)

                self.console.config(state=tk.DISABLED)

        except queue.Empty:
            pass
        finally:
            # Schedule next check
            self.root.after(100, self._process_log_queue)

    def _clear_console(self):
        """Clear console output"""
        self.console.config(state=tk.NORMAL)
        self.console.delete(1.0, tk.END)
        self.console.config(state=tk.DISABLED)

    def _create_backtest_tab(self, parent):
        """Create backtest tab with TLDR section"""
        if not BACKTEST_AVAILABLE:
            ttk.Label(parent, text="Backtesting not available - MT5 modules not installed",
                     font=('Arial', 12)).pack(pady=50)
            return

        # Main container with scrollbar
        main_canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)

        # === TLDR SECTION ===
        tldr_frame = ttk.LabelFrame(scrollable_frame, text="TLDR - Quick Summary", padding=15)
        tldr_frame.pack(fill=tk.X, padx=10, pady=10)

        # Big metrics display
        self.tldr_widgets = {}
        metrics_grid = ttk.Frame(tldr_frame)
        metrics_grid.pack(fill=tk.X)

        tldr_metrics = [
            ("Best Pair", "best_pair", "--"),
            ("Win Rate", "win_rate", "--"),
            ("Net Profit", "net_profit", "--"),
            ("Return %", "return_pct", "--"),
            ("Total Trades", "total_trades", "--"),
            ("Profit Factor", "profit_factor", "--"),
        ]

        for i, (label, key, default) in enumerate(tldr_metrics):
            row = i // 3
            col = i % 3

            metric_frame = ttk.Frame(metrics_grid, relief=tk.RIDGE, borderwidth=2)
            metric_frame.grid(row=row, column=col, padx=10, pady=10, sticky='ew')

            ttk.Label(metric_frame, text=label, font=('Arial', 10, 'bold'),
                     foreground='#666').pack(pady=(5, 0))
            value_label = ttk.Label(metric_frame, text=default, font=('Arial', 18, 'bold'))
            value_label.pack(pady=(0, 5))
            self.tldr_widgets[key] = value_label

        # Make columns equal width
        for col in range(3):
            metrics_grid.columnconfigure(col, weight=1)

        # === CONFIGURATION SECTION ===
        config_frame = ttk.LabelFrame(scrollable_frame, text="Backtest Configuration", padding=15)
        config_frame.pack(fill=tk.X, padx=10, pady=10)

        # Configuration grid
        self.backtest_inputs = {}

        # Row 1: Symbols
        ttk.Label(config_frame, text="Symbols (comma-separated):",
                 font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
        symbols_entry = ttk.Entry(config_frame, width=40)
        symbols_entry.insert(0, "EURUSD,GBPUSD,USDJPY,AUDUSD")
        symbols_entry.grid(row=0, column=1, sticky='ew', padx=10, pady=5)
        self.backtest_inputs['symbols'] = symbols_entry

        # Row 2: Timeframe and Days
        ttk.Label(config_frame, text="Timeframe:",
                 font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
        timeframe_frame = ttk.Frame(config_frame)
        timeframe_frame.grid(row=1, column=1, sticky='ew', padx=10, pady=5)

        timeframe_var = tk.StringVar(value="M15")
        self.backtest_inputs['timeframe'] = timeframe_var
        for tf in ["M15", "M30", "H1", "H4", "D1"]:
            ttk.Radiobutton(timeframe_frame, text=tf, variable=timeframe_var,
                          value=tf).pack(side=tk.LEFT, padx=5)

        # Row 3: Days and Balance
        ttk.Label(config_frame, text="Days to backtest:",
                 font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=5)
        days_frame = ttk.Frame(config_frame)
        days_frame.grid(row=2, column=1, sticky='ew', padx=10, pady=5)

        days_entry = ttk.Entry(days_frame, width=15)
        days_entry.insert(0, "90")
        days_entry.pack(side=tk.LEFT)
        self.backtest_inputs['days'] = days_entry

        ttk.Label(days_frame, text="Initial Balance:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=(20, 5))
        balance_entry = ttk.Entry(days_frame, width=15)
        balance_entry.insert(0, "10000")
        balance_entry.pack(side=tk.LEFT)
        self.backtest_inputs['balance'] = balance_entry

        config_frame.columnconfigure(1, weight=1)

        # === RUN BUTTON ===
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        self.run_backtest_button = ttk.Button(button_frame, text="Run Backtest",
                                              command=self._run_backtest,
                                              style='Success.TButton')
        self.run_backtest_button.pack(side=tk.LEFT, padx=5)

        self.stop_backtest_button = ttk.Button(button_frame, text="Stop",
                                               command=self._stop_backtest,
                                               state=tk.DISABLED,
                                               style='Danger.TButton')
        self.stop_backtest_button.pack(side=tk.LEFT, padx=5)

        # Progress bar and status
        progress_container = ttk.Frame(button_frame)
        progress_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        self.backtest_status_label = ttk.Label(progress_container, text="Ready",
                                               font=('Arial', 9))
        self.backtest_status_label.pack(fill=tk.X)

        self.backtest_progress = ttk.Progressbar(progress_container, mode='determinate')
        self.backtest_progress.pack(fill=tk.X)

        # === CHART SECTION ===
        if MATPLOTLIB_AVAILABLE:
            chart_frame = ttk.LabelFrame(scrollable_frame, text="Equity Curve", padding=15)
            chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Create matplotlib figure
            self.backtest_figure = Figure(figsize=(10, 4), dpi=100)
            self.backtest_ax = self.backtest_figure.add_subplot(111)
            self.backtest_ax.set_title("Equity Curve", fontsize=14, fontweight='bold')
            self.backtest_ax.set_xlabel("Time")
            self.backtest_ax.set_ylabel("Balance ($)")
            self.backtest_ax.grid(True, alpha=0.3)

            self.backtest_canvas = FigureCanvasTkAgg(self.backtest_figure, chart_frame)
            self.backtest_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # === RESULTS TABLE ===
        results_frame = ttk.LabelFrame(scrollable_frame, text="Multi-Symbol Comparison", padding=15)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Scrollable results table
        results_scroll = ttk.Scrollbar(results_frame)
        results_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        columns = ("Symbol", "Trades", "Win%", "Net Profit", "Return%", "Max DD%", "P.Factor")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show='headings',
                                         height=10, yscrollcommand=results_scroll.set)
        results_scroll.config(command=self.results_tree.yview)

        # Configure columns
        col_widths = {"Symbol": 100, "Trades": 80, "Win%": 80, "Net Profit": 120,
                     "Return%": 100, "Max DD%": 100, "P.Factor": 100}

        for col in columns:
            self.results_tree.heading(col, text=col, anchor='w')
            self.results_tree.column(col, width=col_widths.get(col, 100), anchor='w')

        self.results_tree.pack(fill=tk.BOTH, expand=True)

        # Pack scrollbar
        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _run_backtest(self):
        """Run backtest on selected symbols"""
        if self.is_backtesting:
            return

        try:
            # Get configuration
            symbols = [s.strip() for s in self.backtest_inputs['symbols'].get().split(',') if s.strip()]
            timeframe = self.backtest_inputs['timeframe'].get()
            days = int(self.backtest_inputs['days'].get())
            balance = float(self.backtest_inputs['balance'].get())

            if not symbols:
                messagebox.showerror("Error", "Please enter at least one symbol")
                return

            # Update UI
            self.run_backtest_button.config(state=tk.DISABLED)
            self.stop_backtest_button.config(state=tk.NORMAL)
            self.backtest_progress['value'] = 0
            self.backtest_progress['maximum'] = 100
            self.backtest_status_label.config(text="Starting backtest...")
            self.is_backtesting = True

            # Clear previous results
            self.backtest_results = []
            self._clear_backtest_results()

            # Run backtest in separate thread
            self.backtest_thread = threading.Thread(
                target=self._backtest_loop,
                args=(symbols, timeframe, days, balance),
                daemon=True
            )
            self.backtest_thread.start()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start backtest: {e}")
            self._stop_backtest()

    def _stop_backtest(self):
        """Stop backtest"""
        self.is_backtesting = False
        self.run_backtest_button.config(state=tk.NORMAL)
        self.stop_backtest_button.config(state=tk.DISABLED)
        self.backtest_progress['value'] = 0
        self.backtest_status_label.config(text="Ready")

    def _backtest_loop(self, symbols: List[str], timeframe: str, days: int, balance: float):
        """Run backtest loop in separate thread"""
        try:
            # Connect to MT5
            data_loader = BacktestDataLoader()
            if not data_loader.connect_mt5():
                messagebox.showerror("Error", "Failed to connect to MT5")
                self.root.after(0, self._stop_backtest)
                return

            total_symbols = len(symbols)

            # Run backtests for each symbol
            for idx, symbol in enumerate(symbols, 1):
                if not self.is_backtesting:
                    break

                # Update status
                progress_pct = ((idx - 1) / total_symbols) * 100
                status_msg = f"Testing {symbol} ({idx}/{total_symbols})..."
                self.root.after(0, lambda p=progress_pct, s=status_msg: self._update_backtest_progress(p, s))

                # Load data
                historical_data = data_loader.load_historical_data(symbol, timeframe, days)
                if historical_data.empty:
                    # Update status for skipped symbol
                    progress_pct = (idx / total_symbols) * 100
                    status_msg = f"Skipped {symbol} (no data) - {idx}/{total_symbols} complete"
                    self.root.after(0, lambda p=progress_pct, s=status_msg: self._update_backtest_progress(p, s))
                    continue

                # Run backtest
                engine = BacktestEngine(symbol, balance)
                results = engine.run_backtest(historical_data)

                if results:
                    self.backtest_results.append(results)
                    # Update UI from main thread
                    self.root.after(0, lambda r=results: self._update_backtest_display(r))

                # Update progress after completion
                progress_pct = (idx / total_symbols) * 100
                status_msg = f"Completed {symbol} - {idx}/{total_symbols} complete ({progress_pct:.0f}%)"
                self.root.after(0, lambda p=progress_pct, s=status_msg: self._update_backtest_progress(p, s))

            # Disconnect
            data_loader.disconnect_mt5()

            # Final update
            self.root.after(0, lambda: self._update_backtest_progress(100, "Finalizing results..."))
            self.root.after(0, self._finalize_backtest_display)

        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: messagebox.showerror("Error", f"Backtest error: {error_msg}"))
        finally:
            self.root.after(0, self._stop_backtest)

    def _update_backtest_progress(self, progress: float, status: str):
        """Update progress bar and status label"""
        self.backtest_progress['value'] = progress
        self.backtest_status_label.config(text=status)

    def _update_backtest_display(self, results: BacktestResults):
        """Update display with new backtest results"""
        # Add to results table
        net_profit = results.final_balance - results.initial_balance
        return_pct = (results.final_balance / results.initial_balance - 1) * 100

        self.results_tree.insert('', 'end', values=(
            results.symbol,
            results.total_trades,
            f"{results.win_rate:.1f}%",
            f"${net_profit:,.2f}",
            f"{return_pct:.2f}%",
            f"{results.max_drawdown_pct:.2f}%",
            f"{results.profit_factor:.2f}"
        ))

        # Update chart if available
        if MATPLOTLIB_AVAILABLE and results.equity_curve:
            self.backtest_ax.clear()
            self.backtest_ax.set_title("Equity Curve", fontsize=14, fontweight='bold')
            self.backtest_ax.set_xlabel("Bars")
            self.backtest_ax.set_ylabel("Balance ($)")
            self.backtest_ax.grid(True, alpha=0.3)

            # Plot equity curve
            self.backtest_ax.plot(results.equity_curve, label=results.symbol, linewidth=2)
            self.backtest_ax.axhline(y=results.initial_balance, color='gray',
                                    linestyle='--', alpha=0.5, label='Initial Balance')
            self.backtest_ax.legend()
            self.backtest_canvas.draw()

    def _finalize_backtest_display(self):
        """Finalize display after all backtests complete"""
        if not self.backtest_results:
            messagebox.showinfo("Info", "No results to display")
            return

        # Sort by net profit
        sorted_results = sorted(self.backtest_results,
                               key=lambda x: x.final_balance - x.initial_balance,
                               reverse=True)

        # Update TLDR section with best pair
        best = sorted_results[0]
        net_profit = best.final_balance - best.initial_balance
        return_pct = (best.final_balance / best.initial_balance - 1) * 100

        self.tldr_widgets['best_pair'].config(text=best.symbol, foreground='#00AA00')
        self.tldr_widgets['win_rate'].config(text=f"{best.win_rate:.1f}%",
                                            foreground='#00AA00' if best.win_rate > 50 else '#AA0000')
        self.tldr_widgets['net_profit'].config(text=f"${net_profit:,.0f}",
                                              foreground='#00AA00' if net_profit > 0 else '#AA0000')
        self.tldr_widgets['return_pct'].config(text=f"{return_pct:.1f}%",
                                              foreground='#00AA00' if return_pct > 0 else '#AA0000')
        self.tldr_widgets['total_trades'].config(text=str(best.total_trades))
        self.tldr_widgets['profit_factor'].config(text=f"{best.profit_factor:.2f}",
                                                 foreground='#00AA00' if best.profit_factor > 1 else '#AA0000')

        # Update chart with all equity curves
        if MATPLOTLIB_AVAILABLE:
            self.backtest_ax.clear()
            self.backtest_ax.set_title("Equity Curves - All Symbols", fontsize=14, fontweight='bold')
            self.backtest_ax.set_xlabel("Bars")
            self.backtest_ax.set_ylabel("Balance ($)")
            self.backtest_ax.grid(True, alpha=0.3)

            for result in self.backtest_results:
                if result.equity_curve:
                    self.backtest_ax.plot(result.equity_curve, label=result.symbol, linewidth=2)

            self.backtest_ax.axhline(y=best.initial_balance, color='gray',
                                    linestyle='--', alpha=0.5, label='Initial Balance')
            self.backtest_ax.legend()
            self.backtest_canvas.draw()

        messagebox.showinfo("Success", f"Backtest completed!\n\nBest pair: {best.symbol}\n"
                                      f"Win rate: {best.win_rate:.1f}%\n"
                                      f"Net profit: ${net_profit:,.2f}")

    def _clear_backtest_results(self):
        """Clear backtest results display"""
        # Clear table
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        # Clear TLDR
        for widget in self.tldr_widgets.values():
            widget.config(text="--", foreground='black')

        # Clear chart
        if MATPLOTLIB_AVAILABLE:
            self.backtest_ax.clear()
            self.backtest_ax.set_title("Equity Curve", fontsize=14, fontweight='bold')
            self.backtest_ax.set_xlabel("Bars")
            self.backtest_ax.set_ylabel("Balance ($)")
            self.backtest_ax.grid(True, alpha=0.3)
            self.backtest_canvas.draw()

    def _create_debug_tab(self, parent):
        """Create live debug monitoring tab"""
        # Main container
        main_container = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Top section - System State & Connection Status
        top_section = ttk.Frame(main_container)
        main_container.add(top_section, weight=1)

        # System State Panel
        state_frame = ttk.LabelFrame(top_section, text="System State", padding=10)
        state_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.debug_state_labels = {}
        state_items = [
            ("Trading Active", "trading_active"),
            ("MT5 Connected", "mt5_connected"),
            ("Account Balance", "account_balance"),
            ("Account Equity", "account_equity"),
            ("Margin Free", "margin_free"),
            ("Margin Level", "margin_level"),
            ("Open Positions", "open_positions"),
            ("Total Orders", "total_orders"),
            ("Last Update", "last_update"),
        ]

        for label, key in state_items:
            row = ttk.Frame(state_frame)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"{label}:", width=18, anchor='w', font=('Arial', 9, 'bold')).pack(side=tk.LEFT)
            value_label = ttk.Label(row, text="--", anchor='w', font=('Arial', 9))
            value_label.pack(side=tk.LEFT, padx=5)
            self.debug_state_labels[key] = value_label

        # Connection Diagnostics Panel
        diag_frame = ttk.LabelFrame(top_section, text="Connection Diagnostics", padding=10)
        diag_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.debug_diag_labels = {}
        diag_items = [
            ("MT5 Terminal", "mt5_terminal"),
            ("MT5 Version", "mt5_version"),
            ("Account Server", "account_server"),
            ("Account Number", "account_number"),
            ("Account Currency", "account_currency"),
            ("Reconnect Attempts", "reconnect_attempts"),
            ("Last Error", "last_error"),
            ("Trading Allowed", "trading_allowed"),
            ("Expert Enabled", "expert_enabled"),
        ]

        for label, key in diag_items:
            row = ttk.Frame(diag_frame)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"{label}:", width=18, anchor='w', font=('Arial', 9, 'bold')).pack(side=tk.LEFT)
            value_label = ttk.Label(row, text="--", anchor='w', font=('Arial', 9))
            value_label.pack(side=tk.LEFT, padx=5)
            self.debug_diag_labels[key] = value_label

        # Middle section - Active Positions & Orders
        middle_section = ttk.Frame(main_container)
        main_container.add(middle_section, weight=2)

        # Active Positions Table
        positions_frame = ttk.LabelFrame(middle_section, text="Active Positions (Live)", padding=10)
        positions_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        positions_scroll = ttk.Scrollbar(positions_frame)
        positions_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        pos_columns = ("Ticket", "Symbol", "Type", "Volume", "Open Price", "Current Price", "P&L", "Time")
        self.positions_tree = ttk.Treeview(positions_frame, columns=pos_columns, show='headings',
                                          height=8, yscrollcommand=positions_scroll.set)
        positions_scroll.config(command=self.positions_tree.yview)

        for col in pos_columns:
            self.positions_tree.heading(col, text=col, anchor='w')
            self.positions_tree.column(col, width=100, anchor='w')

        self.positions_tree.pack(fill=tk.BOTH, expand=True)

        # Recent Orders Table
        orders_frame = ttk.LabelFrame(middle_section, text="Recent Orders (Last 20)", padding=10)
        orders_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        orders_scroll = ttk.Scrollbar(orders_frame)
        orders_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        order_columns = ("Time", "Ticket", "Symbol", "Type", "Volume", "Price", "Status")
        self.orders_tree = ttk.Treeview(orders_frame, columns=order_columns, show='headings',
                                       height=8, yscrollcommand=orders_scroll.set)
        orders_scroll.config(command=self.orders_tree.yview)

        for col in order_columns:
            self.orders_tree.heading(col, text=col, anchor='w')
            self.orders_tree.column(col, width=100, anchor='w')

        self.orders_tree.pack(fill=tk.BOTH, expand=True)

        # Bottom section - Debug Log
        bottom_section = ttk.Frame(main_container)
        main_container.add(bottom_section, weight=2)

        debug_log_frame = ttk.LabelFrame(bottom_section, text="Debug Log (Detailed)", padding=10)
        debug_log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Debug log text area
        self.debug_console = scrolledtext.ScrolledText(debug_log_frame, height=15,
                                                       bg='#0a0a0a', fg='#00ff00',
                                                       font=('Consolas', 8))
        self.debug_console.pack(fill=tk.BOTH, expand=True)
        self.debug_console.config(state=tk.DISABLED)

        # Debug console controls
        debug_controls = ttk.Frame(debug_log_frame)
        debug_controls.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(debug_controls, text="Clear Debug Log",
                  command=self._clear_debug_console).pack(side=tk.LEFT, padx=5)

        self.debug_autoscroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(debug_controls, text="Auto-scroll",
                       variable=self.debug_autoscroll_var).pack(side=tk.LEFT, padx=5)

        ttk.Button(debug_controls, text="Export Debug History",
                  command=self._export_debug_history).pack(side=tk.LEFT, padx=5)

        ttk.Button(debug_controls, text="Refresh Now",
                  command=self._force_debug_update).pack(side=tk.LEFT, padx=5)

        # Filter controls
        ttk.Label(debug_controls, text="Filter:").pack(side=tk.LEFT, padx=(20, 5))
        self.debug_filter_var = tk.StringVar()
        filter_combo = ttk.Combobox(debug_controls, textvariable=self.debug_filter_var,
                                   values=["ALL", "INFO", "WARNING", "ERROR", "SUCCESS", "DEBUG"],
                                   width=10, state='readonly')
        filter_combo.set("ALL")
        filter_combo.pack(side=tk.LEFT, padx=5)

        # Start debug queue processor
        self._process_debug_queue()

        # Add initial debug message
        self._add_debug_log("Debug tab initialized - ready for live monitoring", "success")

    def _clear_debug_console(self):
        """Clear debug console output"""
        self.debug_console.config(state=tk.NORMAL)
        self.debug_console.delete(1.0, tk.END)
        self.debug_console.config(state=tk.DISABLED)
        self.debug_history.clear()

    def _export_debug_history(self):
        """Export debug history to file"""
        if not self.debug_history:
            messagebox.showinfo("Info", "No debug history to export")
            return

        try:
            filename = f"debug_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, 'w') as f:
                f.write("=" * 80 + "\n")
                f.write(f"Ganymede Trade City - Debug Log Export\n")
                f.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
                for timestamp, message, level in self.debug_history:
                    f.write(f"[{timestamp}] [{level.upper()}] {message}\n")

            messagebox.showinfo("Success", f"Debug history exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")

    def _force_debug_update(self):
        """Force update of all debug information"""
        if self.is_trading and self.trade_manager:
            try:
                self._update_debug_info()
                self._add_debug_log("Manual refresh triggered", "info")
            except Exception as e:
                self._add_debug_log(f"Error during manual refresh: {e}", "error")
        else:
            messagebox.showinfo("Info", "No active trading session to debug")

    def _add_debug_log(self, message: str, level: str = "info"):
        """Add message to debug log (thread-safe)"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.debug_queue.put((timestamp, message, level))

        # Store in history
        if len(self.debug_history) >= self.max_debug_history:
            self.debug_history.pop(0)
        self.debug_history.append((timestamp, message, level))

    def _process_debug_queue(self):
        """Process debug messages from queue and update console"""
        try:
            while True:
                timestamp, message, level = self.debug_queue.get_nowait()

                # Apply filter
                filter_value = self.debug_filter_var.get() if hasattr(self, 'debug_filter_var') else "ALL"
                if filter_value != "ALL" and level.upper() != filter_value:
                    continue

                # Color coding
                color_map = {
                    'info': '#00ff00',
                    'success': '#00ff00',
                    'warning': '#ffaa00',
                    'error': '#ff0000',
                    'debug': '#00aaff',
                }
                color = color_map.get(level, '#00ff00')

                # Add to debug console
                self.debug_console.config(state=tk.NORMAL)
                self.debug_console.insert(tk.END, f"[{timestamp}] ", 'timestamp')
                self.debug_console.insert(tk.END, f"[{level.upper()}] ", f'level_{level}')
                self.debug_console.insert(tk.END, f"{message}\n", level)

                # Apply color tags
                self.debug_console.tag_config('timestamp', foreground='#666666')
                self.debug_console.tag_config(f'level_{level}', foreground=color, font=('Consolas', 8, 'bold'))
                self.debug_console.tag_config(level, foreground=color)

                # Auto-scroll if enabled
                if hasattr(self, 'debug_autoscroll_var') and self.debug_autoscroll_var.get():
                    self.debug_console.see(tk.END)

                self.debug_console.config(state=tk.DISABLED)

        except queue.Empty:
            pass
        finally:
            # Schedule next check
            self.root.after(50, self._process_debug_queue)

    def _update_debug_info(self):
        """Update all debug information from trade manager (thread-safe)"""
        if not self.trade_manager or not self.is_trading:
            return

        try:
            # Update system state
            if self.trade_manager.mt5_connected:
                import MetaTrader5 as mt5
                account_info = mt5.account_info()
                terminal_info = mt5.terminal_info()

                if account_info:
                    self.root.after(0, self._update_debug_state, 'account_balance', f"${account_info.balance:,.2f}")
                    self.root.after(0, self._update_debug_state, 'account_equity', f"${account_info.equity:,.2f}")
                    self.root.after(0, self._update_debug_state, 'margin_free', f"${account_info.margin_free:,.2f}")
                    margin_level = account_info.margin_level if account_info.margin_level else 0
                    self.root.after(0, self._update_debug_state, 'margin_level', f"{margin_level:.2f}%")

                if terminal_info:
                    self.root.after(0, self._update_debug_diag, 'mt5_terminal', terminal_info.name)
                    self.root.after(0, self._update_debug_diag, 'mt5_version', str(terminal_info.build))
                    self.root.after(0, self._update_debug_diag, 'trading_allowed', "Yes" if terminal_info.trade_allowed else "No")
                    self.root.after(0, self._update_debug_diag, 'expert_enabled', "Yes" if terminal_info.mqid else "No")

                if account_info:
                    self.root.after(0, self._update_debug_diag, 'account_server', account_info.server)
                    self.root.after(0, self._update_debug_diag, 'account_number', str(account_info.login))
                    self.root.after(0, self._update_debug_diag, 'account_currency', account_info.currency)

                # Get positions
                positions = mt5.positions_get()
                if positions:
                    self.root.after(0, self._update_debug_state, 'open_positions', str(len(positions)))
                    self.root.after(0, self._update_positions_table, positions)
                else:
                    self.root.after(0, self._update_debug_state, 'open_positions', "0")
                    self.root.after(0, self._clear_positions_table)

                # Get recent orders
                from datetime import datetime, timedelta
                history_orders = mt5.history_orders_get(
                    datetime.now() - timedelta(days=1),
                    datetime.now()
                )
                if history_orders:
                    self.root.after(0, self._update_debug_state, 'total_orders', str(len(history_orders)))
                    self.root.after(0, self._update_orders_table, history_orders[-20:])  # Last 20
                else:
                    self.root.after(0, self._update_debug_state, 'total_orders', "0")

            self.root.after(0, self._update_debug_state, 'trading_active', "Yes" if self.is_trading else "No")
            self.root.after(0, self._update_debug_state, 'mt5_connected', "Yes" if self.trade_manager.mt5_connected else "No")
            self.root.after(0, self._update_debug_state, 'last_update', datetime.now().strftime("%H:%M:%S"))
            self.root.after(0, self._update_debug_diag, 'reconnect_attempts', "0")
            self.root.after(0, self._update_debug_diag, 'last_error', "None")

        except Exception as e:
            self._add_debug_log(f"Error updating debug info: {e}", "error")

    def _update_debug_state(self, key: str, value: str):
        """Update a debug state label"""
        if key in self.debug_state_labels:
            self.debug_state_labels[key].config(text=value)

    def _update_debug_diag(self, key: str, value: str):
        """Update a debug diagnostic label"""
        if key in self.debug_diag_labels:
            self.debug_diag_labels[key].config(text=value)

    def _update_positions_table(self, positions):
        """Update positions table with current positions"""
        # Clear existing
        for item in self.positions_tree.get_children():
            self.positions_tree.delete(item)

        # Add positions
        for pos in positions:
            pos_type = "BUY" if pos.type == 0 else "SELL"
            pnl_color = 'green' if pos.profit > 0 else 'red'
            time_str = datetime.fromtimestamp(pos.time).strftime("%H:%M:%S")

            self.positions_tree.insert('', 'end', values=(
                pos.ticket,
                pos.symbol,
                pos_type,
                pos.volume,
                f"{pos.price_open:.5f}",
                f"{pos.price_current:.5f}",
                f"${pos.profit:.2f}",
                time_str
            ), tags=(pnl_color,))

        # Configure tags
        self.positions_tree.tag_configure('green', foreground='#00AA00')
        self.positions_tree.tag_configure('red', foreground='#AA0000')

    def _clear_positions_table(self):
        """Clear positions table"""
        for item in self.positions_tree.get_children():
            self.positions_tree.delete(item)

    def _update_orders_table(self, orders):
        """Update orders table with recent orders"""
        # Clear existing
        for item in self.orders_tree.get_children():
            self.orders_tree.delete(item)

        # Add orders
        for order in orders:
            order_type = "BUY" if order.type == 0 else "SELL"
            time_str = datetime.fromtimestamp(order.time_setup).strftime("%H:%M:%S")

            # Determine status
            status_map = {
                0: "PLACED",
                1: "FILLED",
                2: "CANCELED",
                3: "PARTIAL",
                4: "REJECTED",
            }
            status = status_map.get(order.state, "UNKNOWN")

            self.orders_tree.insert('', 'end', values=(
                time_str,
                order.ticket,
                order.symbol,
                order_type,
                order.volume_initial,
                f"{order.price_open:.5f}",
                status
            ))


def main():
    """Main entry point"""
    root = tk.Tk()

    # Configure styles
    style = ttk.Style()
    style.theme_use('clam')

    # Custom button styles
    style.configure('Success.TButton', foreground='green')
    style.configure('Danger.TButton', foreground='red')

    # Create and run GUI
    app = TradingGUI(root)

    # Handle window close
    def on_closing():
        if app.is_trading:
            if messagebox.askokcancel("Quit", "Trading is active. Stop and quit?"):
                app._stop_trading()
                root.destroy()
        else:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
