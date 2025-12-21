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
try:
    from trade_manager import TradeManager
    import trading_config as config
except ImportError:
    print("[ERROR] Could not import trading_system modules")
    print("Make sure trade_manager.py and trading_config.py are in the same directory")
    sys.exit(1)


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

            # Take Profit & Stop Loss (ADDED TP PARAMETER!)
            'take_profit_pips': config.TAKE_PROFIT_PIPS,
            'stop_loss_pips': config.STOP_LOSS_PIPS,

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
        self.trading_lock = threading.Lock()
        self.log_queue = queue.Queue()

        # Build UI
        self._create_ui()

        # Load saved configuration into UI
        self._load_config_to_ui()

        # Start log queue processor
        self._process_log_queue()

    def _create_ui(self):
        """Create the user interface"""
        # Create main tab
        self.trading_tab = ttk.Frame(self.root)
        self.trading_tab.pack(fill=tk.BOTH, expand=True)
        self._create_live_trading_tab(self.trading_tab)

    def _create_live_trading_tab(self, parent):
        """Create live trading tab content"""
        main_container = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel - Parameters
        left_panel = ttk.Frame(main_container)
        main_container.add(left_panel, weight=1)

        # Right panel - Console and Stats
        right_panel = ttk.Frame(main_container)
        main_container.add(right_panel, weight=2)

        # Create panels
        self._create_parameters_panel(left_panel)
        self._create_console_panel(right_panel)

    def _create_parameters_panel(self, parent):
        """Create parameters configuration panel"""
        title = ttk.Label(parent, text="Trading Parameters", font=('Arial', 14, 'bold'))
        title.pack(pady=10)

        # Scrollable frame
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        self.entries = {}

        # MT5 Credentials
        self._create_section(scrollable_frame, "MT5 Connection", [
            ("MT5 Login", 'mt5_login', 'text'),
            ("MT5 Password", 'mt5_password', 'password'),
            ("MT5 Server", 'mt5_server', 'text'),
        ])

        # Grid Parameters
        self._create_section(scrollable_frame, "Grid Strategy", [
            ("Grid Spacing (pips)", 'grid_spacing_pips', 'float'),
            ("Max Grid Levels", 'max_grid_levels', 'int'),
            ("Grid Lot Size", 'grid_lot_size', 'float'),
        ])

        # Take Profit & Stop Loss (ADDED SECTION!)
        self._create_section(scrollable_frame, "Take Profit & Stop Loss", [
            ("Take Profit (pips)", 'take_profit_pips', 'float'),
            ("Stop Loss (pips)", 'stop_loss_pips', 'float'),
        ])

        # Hedge Parameters
        self._create_section(scrollable_frame, "Hedge Strategy", [
            ("Hedge Ratio (x)", 'hedge_ratio', 'float'),
            ("Hedge Trigger (pips)", 'hedge_trigger_pips', 'int'),
        ])

        # Recovery Parameters
        self._create_section(scrollable_frame, "Recovery Strategy", [
            ("Martingale Multiplier", 'martingale_multiplier', 'float'),
            ("Max Recovery Levels", 'max_recovery_levels', 'int'),
        ])

        # Confluence Parameters
        self._create_section(scrollable_frame, "Confluence Filters", [
            ("Min Confluence Score", 'min_confluence_score', 'int'),
            ("Confluence Tolerance (%)", 'confluence_tolerance_pct', 'float'),
        ])

        # Risk Parameters
        self._create_section(scrollable_frame, "Risk Management", [
            ("Max Drawdown (%)", 'max_drawdown_pct', 'float'),
            ("Daily Loss Limit (%)", 'daily_loss_limit_pct', 'float'),
            ("Max Consecutive Losses", 'max_consecutive_losses', 'int'),
            ("Max Positions per Symbol", 'max_positions_per_symbol', 'int'),
        ])

        # Trading Parameters
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
        """Create a parameter section"""
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
        # Statistics
        stats_frame = ttk.LabelFrame(parent, text="Live Statistics", padding=10)
        stats_frame.pack(fill=tk.X, padx=5, pady=5)

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
                                       command=self._start_trading)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(control_frame, text="Stop Trading",
                                      command=self._stop_trading, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Console
        console_frame = ttk.LabelFrame(parent, text="Trading Console", padding=10)
        console_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.console = scrolledtext.ScrolledText(console_frame, height=20,
                                                  bg='#1e1e1e', fg='#00ff00',
                                                  font=('Consolas', 9))
        self.console.pack(fill=tk.BOTH, expand=True)
        self.console.config(state=tk.DISABLED)

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
                messagebox.showinfo("Success", "Configuration saved!")
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
        messagebox.showinfo("Success", "Configuration loaded!")

    def _reset_to_defaults(self):
        """Reset all parameters to default values"""
        if messagebox.askyesno("Confirm Reset",
                               "Reset all parameters to default values?"):
            self.config = self.config_manager._get_default_config()
            self._load_config_to_ui()
            self._log("Configuration reset to defaults", "info")

    def _start_trading(self):
        """Start the trading system"""
        with self.trading_lock:
            if self.is_trading:
                return

        try:
            # Save current configuration
            self._save_configuration()

            # Validate MT5 credentials
            if not all([self.config.get('mt5_login'),
                       self.config.get('mt5_password'),
                       self.config.get('mt5_server')]):
                messagebox.showerror("Error", "Please configure MT5 credentials")
                return

            # Cleanup old connection
            if self.trade_manager:
                try:
                    self.trade_manager.disconnect_mt5()
                    import time
                    time.sleep(0.5)
                except:
                    pass
                self.trade_manager = None

            # Update UI
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)

            with self.trading_lock:
                self.is_trading = True

            self._update_stat('status', '[RUNNING]')

            # Start trading thread
            self.trading_thread = threading.Thread(target=self._trading_loop, daemon=True)
            self.trading_thread.start()

            self._log("=" * 60, "info")
            self._log("TRADING SYSTEM STARTED", "success")
            self._log("=" * 60, "info")

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

        self._reset_ui_after_stop()

        self._log("=" * 60, "info")
        self._log("TRADING SYSTEM STOPPED", "warning")
        self._log("=" * 60, "info")

    def _reset_ui_after_stop(self):
        """Reset UI after trading stops"""
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self._update_stat('status', '[STOPPED]')

    def _trading_loop(self):
        """Main trading loop"""
        try:
            # Initialize trade manager with runtime config (CRITICAL FIX!)
            self.trade_manager = TradeManager(
                symbols=self.config['symbols'],
                timeframe=self.config.get('timeframe', 'M15'),
                log_callback=self._log,
                runtime_config=self.config  # PASS CONFIG HERE!
            )

            # Connect to MT5
            self._log("Connecting to MT5...", "info")
            if not self.trade_manager.connect_mt5(
                login=int(self.config['mt5_login']),
                password=self.config['mt5_password'],
                server=self.config['mt5_server']
            ):
                self._log("[ERROR] Failed to connect to MT5", "error")
                self.is_trading = False
                self.root.after(0, self._reset_ui_after_stop)
                return

            self._log("Connected to MT5 successfully", "success")

            # Trading loop
            interval = self.config.get('update_interval_seconds', 60)

            while self.is_trading:
                try:
                    if not self.trade_manager.mt5_connected:
                        self._log("[WARNING] MT5 disconnected. Attempting reconnect...", "warning")
                        if self.trade_manager.connect_mt5(
                            login=int(self.config['mt5_login']),
                            password=self.config['mt5_password'],
                            server=self.config['mt5_server']
                        ):
                            self._log("[SUCCESS] Reconnected to MT5", "success")
                        else:
                            self._log("[ERROR] Reconnection failed", "error")
                            threading.Event().wait(10)
                            continue

                    self.trade_manager.run_trading_cycle()
                    self._update_statistics()

                    for _ in range(interval):
                        if not self.is_trading:
                            break
                        threading.Event().wait(1)

                except Exception as e:
                    self._log(f"[ERROR] Trading cycle error: {e}", "error")
                    import traceback
                    self._log(f"[DEBUG] {traceback.format_exc()}", "error")
                    threading.Event().wait(5)

            # Cleanup
            self._log("Closing positions and disconnecting...", "info")
            if self.trade_manager:
                self.trade_manager.disconnect_mt5()

        except Exception as e:
            self._log(f"[ERROR] Fatal error: {e}", "error")
        finally:
            self.is_trading = False
            self.root.after(0, self._reset_ui_after_stop)

    def _update_statistics(self):
        """Update statistics display"""
        if not self.trade_manager:
            return

        try:
            stats = self.trade_manager.get_statistics()

            self.root.after(0, self._update_stat, 'positions', str(stats.get('open_positions', 0)))
            self.root.after(0, self._update_stat, 'pnl', f"${stats.get('total_pnl', 0.0):.2f}")
            self.root.after(0, self._update_stat, 'win_rate', f"{stats.get('win_rate', 0.0):.1f}%")
            self.root.after(0, self._update_stat, 'drawdown', f"{stats.get('drawdown', 0.0):.1f}%")
            self.root.after(0, self._update_stat, 'today_trades', str(stats.get('today_trades', 0)))

        except Exception as e:
            self._log(f"Error updating statistics: {e}", "error")

    def _update_stat(self, key: str, value: str):
        """Update a statistic label"""
        if key in self.stats_labels:
            self.stats_labels[key].config(text=value)

    def _log(self, message: str, level: str = "info"):
        """Add message to log queue"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put((timestamp, message, level))

    def _process_log_queue(self):
        """Process log messages from queue"""
        try:
            while True:
                timestamp, message, level = self.log_queue.get_nowait()

                color_map = {
                    'info': '#00ff00',
                    'success': '#00ff00',
                    'warning': '#ffaa00',
                    'error': '#ff0000',
                }
                color = color_map.get(level, '#00ff00')

                self.console.config(state=tk.NORMAL)
                self.console.insert(tk.END, f"[{timestamp}] ", 'timestamp')
                self.console.insert(tk.END, f"{message}\n", level)

                self.console.tag_config('timestamp', foreground='#888888')
                self.console.tag_config(level, foreground=color)

                if self.autoscroll_var.get():
                    self.console.see(tk.END)

                self.console.config(state=tk.DISABLED)

        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._process_log_queue)

    def _clear_console(self):
        """Clear console"""
        self.console.config(state=tk.NORMAL)
        self.console.delete(1.0, tk.END)
        self.console.config(state=tk.DISABLED)


def main():
    """Main entry point"""
    root = tk.Tk()
    app = TradingGUI(root)

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
