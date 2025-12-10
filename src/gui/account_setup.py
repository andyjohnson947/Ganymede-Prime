"""
MT5 Account Setup GUI
Simple GUI for configuring MT5 credentials
"""

import tkinter as tk
from tkinter import ttk, messagebox
import yaml
import logging
from pathlib import Path
from typing import Dict


class AccountSetupGUI:
    """Simple GUI for MT5 account configuration"""

    def __init__(self):
        """Initialize Account Setup GUI"""
        self.logger = logging.getLogger(__name__)
        self.config_path = Path("config/mt5_credentials.yaml")

        # Create main window
        self.root = tk.Tk()
        self.root.title("MT5 Account Setup")
        self.root.geometry("500x400")
        self.root.resizable(False, False)

        # Style
        style = ttk.Style()
        style.theme_use('clam')

        # Variables
        self.login_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.server_var = tk.StringVar()
        self.path_var = tk.StringVar()
        self.timeout_var = tk.IntVar(value=60000)
        self.portable_var = tk.BooleanVar(value=False)

        # Load existing config if available
        self._load_existing_config()

        # Create UI
        self._create_ui()

    def _load_existing_config(self):
        """Load existing configuration if available"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    mt5_config = config.get('mt5', {})

                    self.login_var.set(mt5_config.get('login', ''))
                    self.password_var.set(mt5_config.get('password', ''))
                    self.server_var.set(mt5_config.get('server', ''))
                    self.path_var.set(mt5_config.get('path', ''))
                    self.timeout_var.set(mt5_config.get('timeout', 60000))
                    self.portable_var.set(mt5_config.get('portable', False))

                    self.logger.info("Loaded existing MT5 configuration")
            except Exception as e:
                self.logger.warning(f"Could not load existing config: {e}")

    def _create_ui(self):
        """Create the user interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Title
        title_label = ttk.Label(
            main_frame,
            text="MT5 Account Configuration",
            font=('Arial', 14, 'bold')
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # Login
        ttk.Label(main_frame, text="Login:").grid(row=1, column=0, sticky=tk.W, pady=5)
        login_entry = ttk.Entry(main_frame, textvariable=self.login_var, width=40)
        login_entry.grid(row=1, column=1, pady=5)

        # Password
        ttk.Label(main_frame, text="Password:").grid(row=2, column=0, sticky=tk.W, pady=5)
        password_entry = ttk.Entry(main_frame, textvariable=self.password_var, width=40, show="*")
        password_entry.grid(row=2, column=1, pady=5)

        # Server
        ttk.Label(main_frame, text="Server:").grid(row=3, column=0, sticky=tk.W, pady=5)
        server_entry = ttk.Entry(main_frame, textvariable=self.server_var, width=40)
        server_entry.grid(row=3, column=1, pady=5)
        ttk.Label(main_frame, text="e.g., YourBroker-Demo", font=('Arial', 8), foreground='gray').grid(
            row=4, column=1, sticky=tk.W
        )

        # Path
        ttk.Label(main_frame, text="MT5 Path:").grid(row=5, column=0, sticky=tk.W, pady=5)
        path_entry = ttk.Entry(main_frame, textvariable=self.path_var, width=40)
        path_entry.grid(row=5, column=1, pady=5)
        ttk.Label(main_frame, text="Leave empty for default", font=('Arial', 8), foreground='gray').grid(
            row=6, column=1, sticky=tk.W
        )

        # Timeout
        ttk.Label(main_frame, text="Timeout (ms):").grid(row=7, column=0, sticky=tk.W, pady=5)
        timeout_spinbox = ttk.Spinbox(
            main_frame,
            from_=1000,
            to=300000,
            textvariable=self.timeout_var,
            width=38
        )
        timeout_spinbox.grid(row=7, column=1, pady=5)

        # Portable
        portable_check = ttk.Checkbutton(
            main_frame,
            text="Portable MT5 installation",
            variable=self.portable_var
        )
        portable_check.grid(row=8, column=1, sticky=tk.W, pady=10)

        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=9, column=0, columnspan=2, pady=20)

        # Test connection button
        test_btn = ttk.Button(
            button_frame,
            text="Test Connection",
            command=self._test_connection
        )
        test_btn.grid(row=0, column=0, padx=5)

        # Save button
        save_btn = ttk.Button(
            button_frame,
            text="Save Configuration",
            command=self._save_config
        )
        save_btn.grid(row=0, column=1, padx=5)

        # Cancel button
        cancel_btn = ttk.Button(
            button_frame,
            text="Cancel",
            command=self.root.quit
        )
        cancel_btn.grid(row=0, column=2, padx=5)

    def _validate_inputs(self) -> bool:
        """Validate user inputs"""
        if not self.login_var.get():
            messagebox.showerror("Error", "Login is required")
            return False

        if not self.password_var.get():
            messagebox.showerror("Error", "Password is required")
            return False

        if not self.server_var.get():
            messagebox.showerror("Error", "Server is required")
            return False

        try:
            int(self.login_var.get())
        except ValueError:
            messagebox.showerror("Error", "Login must be a number")
            return False

        return True

    def _test_connection(self):
        """Test MT5 connection"""
        if not self._validate_inputs():
            return

        try:
            import MetaTrader5 as mt5

            # Prepare credentials
            credentials = self._get_credentials()

            # Try to connect
            result = mt5.initialize(
                path=credentials['path'],
                login=credentials['login'],
                password=credentials['password'],
                server=credentials['server'],
                timeout=credentials['timeout'],
                portable=credentials['portable']
            )

            if result:
                account_info = mt5.account_info()
                if account_info:
                    messagebox.showinfo(
                        "Success",
                        f"Connection successful!\n\n"
                        f"Account: {account_info.login}\n"
                        f"Server: {account_info.server}\n"
                        f"Balance: {account_info.balance}"
                    )
                    mt5.shutdown()
                else:
                    messagebox.showerror("Error", "Could not retrieve account info")
                    mt5.shutdown()
            else:
                error = mt5.last_error()
                messagebox.showerror("Error", f"Connection failed: {error}")

        except Exception as e:
            messagebox.showerror("Error", f"Connection test failed: {str(e)}")

    def _get_credentials(self) -> Dict:
        """Get credentials dictionary"""
        return {
            'login': int(self.login_var.get()),
            'password': self.password_var.get(),
            'server': self.server_var.get(),
            'path': self.path_var.get(),
            'timeout': self.timeout_var.get(),
            'portable': self.portable_var.get()
        }

    def _save_config(self):
        """Save configuration to file"""
        if not self._validate_inputs():
            return

        try:
            # Ensure config directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Prepare config
            config = {
                'mt5': self._get_credentials()
            }

            # Save to file
            with open(self.config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)

            messagebox.showinfo(
                "Success",
                f"Configuration saved to:\n{self.config_path}"
            )

            self.logger.info(f"MT5 configuration saved to {self.config_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")
            self.logger.error(f"Failed to save configuration: {e}")

    def run(self):
        """Run the GUI"""
        self.root.mainloop()


def main():
    """Main entry point for GUI"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    app = AccountSetupGUI()
    app.run()


if __name__ == "__main__":
    main()
