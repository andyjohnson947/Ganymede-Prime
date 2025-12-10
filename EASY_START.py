#!/usr/bin/env python3
"""
EA ANALYSIS - ONE CLICK LAUNCHER
No command line needed - just double click!
"""

import os
import sys
import subprocess
from pathlib import Path
import platform

# Enable colors on Windows
if platform.system() == 'Windows':
    try:
        # Try to enable ANSI colors on Windows 10+
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except:
        pass

# Colors for terminal output (disabled on Windows if needed)
USE_COLORS = True
try:
    # Test if colors work
    if platform.system() == 'Windows':
        # Check Windows version
        import sys
        if sys.version_info < (3, 6):
            USE_COLORS = False
except:
    USE_COLORS = False

class Colors:
    if USE_COLORS:
        HEADER = '\033[95m'
        BLUE = '\033[94m'
        CYAN = '\033[96m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        RED = '\033[91m'
        END = '\033[0m'
        BOLD = '\033[1m'
    else:
        HEADER = ''
        BLUE = ''
        CYAN = ''
        GREEN = ''
        YELLOW = ''
        RED = ''
        END = ''
        BOLD = ''

def print_header(text):
    """Print fancy header"""
    print("\n" + "=" * 70)
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.END}")
    print("=" * 70 + "\n")

def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def print_info(text):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")

def check_python_version():
    """Check if Python version is 3.8+"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_error(f"Python 3.8+ required, you have {version.major}.{version.minor}")
        return False
    print_success(f"Python {version.major}.{version.minor}.{version.micro} detected")
    return True

def install_dependencies():
    """Install required packages"""
    print_header("INSTALLING DEPENDENCIES")
    print_info("This may take a few minutes...")

    try:
        # Try to install core requirements
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-q", "--upgrade", "pip"
        ])

        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-q", "-r", "requirements-core.txt"
        ])

        # Try to install MT5
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-q", "MetaTrader5"
            ])
            print_success("MetaTrader5 installed")
        except:
            print_info("MetaTrader5 not available (install manually if needed)")

        print_success("All dependencies installed!")
        return True

    except Exception as e:
        print_error(f"Installation failed: {e}")
        return False

def check_dependencies():
    """Check if dependencies are installed"""
    try:
        import pandas
        import numpy
        import sklearn
        print_success("Dependencies already installed")
        return True
    except ImportError:
        print_info("Dependencies need to be installed")
        return False

def check_mt5_credentials():
    """Check if MT5 credentials are configured"""
    creds_file = Path("config/mt5_credentials.yaml")
    if creds_file.exists():
        print_success("MT5 credentials found")
        return True
    else:
        print_info("MT5 credentials not configured yet")
        return False

def setup_mt5_credentials():
    """Setup MT5 credentials"""
    print_header("MT5 CREDENTIALS SETUP")

    # Try GUI first
    try:
        print_info("Opening credential setup GUI...")
        from src.gui.account_setup import AccountSetupGUI
        app = AccountSetupGUI()
        app.run()
        return True
    except Exception as e:
        # Fallback to console setup
        print_info("GUI not available, using console setup")
        print()

        login = input("Enter your MT5 Login: ").strip()
        password = input("Enter your MT5 Password: ").strip()
        server = input("Enter your MT5 Server (e.g., YourBroker-Demo): ").strip()

        # Create credentials file
        os.makedirs("config", exist_ok=True)

        yaml_content = f"""# MT5 Account Credentials
mt5:
  login: {login}
  password: "{password}"
  server: "{server}"
  path: ""
  timeout: 60000
  portable: false
"""

        with open("config/mt5_credentials.yaml", "w") as f:
            f.write(yaml_content)

        print_success("MT5 credentials saved!")
        return True

def show_menu():
    """Show main menu"""
    print_header("EA ANALYSIS - WHAT DO YOU WANT TO DO?")

    print(f"{Colors.BOLD}1.{Colors.END} {Colors.CYAN}Analyze My EA{Colors.END} (Full multi-timeframe analysis)")
    print(f"{Colors.BOLD}2.{Colors.END} {Colors.CYAN}Analyze Confluence Zones{Colors.END} (Find high-value trade setups)")
    print(f"{Colors.BOLD}3.{Colors.END} {Colors.CYAN}Deep Dive: Recovery Strategies{Colors.END} (Hedge/DCA/Martingale/Timing/Leverage)")
    print(f"{Colors.BOLD}4.{Colors.END} {Colors.CYAN}Generate Strategy Report{Colors.END} (TLDR + Python implementation guide)")
    print(f"{Colors.BOLD}5.{Colors.END} {Colors.CYAN}Test MT5 Connection{Colors.END} (Quick connection test)")
    print(f"{Colors.BOLD}6.{Colors.END} {Colors.CYAN}Analyze a Symbol{Colors.END} (Quick market analysis)")
    print(f"{Colors.BOLD}7.{Colors.END} {Colors.CYAN}Setup MT5 Credentials{Colors.END} (Change login details)")
    print(f"{Colors.BOLD}8.{Colors.END} {Colors.CYAN}Exit{Colors.END}")
    print()

    while True:
        choice = input(f"{Colors.BOLD}Choose option (1-8):{Colors.END} ").strip()
        if choice in ['1', '2', '3', '4', '5', '6', '7', '8']:
            return choice
        print_error("Invalid choice, please enter 1-8")

def run_ea_analysis():
    """Run EA analysis with multi-timeframe analysis"""
    print_header("EA REVERSE ENGINEERING + MULTI-TIMEFRAME ANALYSIS")
    print_info("Starting comprehensive EA monitoring and analysis...")
    print_info("This includes:")
    print_info("  • EA trade monitoring and pattern detection")
    print_info("  • LVN multi-timeframe analysis (Hourly/Daily/Weekly)")
    print_info("  • Session volatility correlation with ATR")
    print_info("  • Previous week institutional levels")
    print_info("  • Recovery success rate tracking")
    print_info("  • Time-based pattern correlation")
    print()

    try:
        # Step 1: Run EA mining
        print_info("Step 1: Running EA reverse engineering...")
        result1 = subprocess.run([sys.executable, "run.py", "--mine-ea"])

        if result1.returncode != 0:
            print_error("EA mining failed")
            return False

        print_success("EA reverse engineering complete!")
        print()

        # Step 2: Run multi-timeframe analysis
        print_info("Step 2: Running multi-timeframe analysis...")
        result2 = subprocess.run([sys.executable, "analyze_multi_timeframe.py"])

        if result2.returncode != 0:
            print_error("Multi-timeframe analysis failed")
            return False

        print_success("Multi-timeframe analysis complete!")
        print()
        print_info("Results saved to:")
        print_info("  • multi_timeframe_analysis.json (detailed)")
        print_info("  • multi_timeframe_summary.csv (summary)")

        return True

    except Exception as e:
        print_error(f"Failed to run EA analysis: {e}")
        return False

def test_mt5_connection():
    """Test MT5 connection"""
    print_header("TESTING MT5 CONNECTION")
    print_info("Attempting to connect to MetaTrader 5...")
    print()

    try:
        result = subprocess.run([
            sys.executable, "run.py", "--analyze", "EURUSD"
        ])
        return result.returncode == 0
    except Exception as e:
        print_error(f"Connection test failed: {e}")
        return False

def analyze_symbol():
    """Analyze a specific symbol"""
    print_header("SYMBOL ANALYSIS")
    print()

    symbol = input("Enter symbol to analyze (e.g., EURUSD): ").strip().upper()
    if not symbol:
        symbol = "EURUSD"

    print_info(f"Analyzing {symbol}...")
    print()

    try:
        result = subprocess.run([
            sys.executable, "run.py", "--analyze", symbol
        ])
        return result.returncode == 0
    except Exception as e:
        print_error(f"Analysis failed: {e}")
        return False

def analyze_confluence_zones():
    """Analyze confluence zones from reverse engineering data"""
    print_header("CONFLUENCE ZONE ANALYSIS")
    print_info("Analyzing high-value overlapping trade setups...")
    print()

    # Check if data file exists
    data_file = Path("ea_reverse_engineering_detailed.csv")
    if not data_file.exists():
        print_error("No reverse engineering data found!")
        print_info("Please run 'Analyze My EA' first to generate the data")
        print()
        return False

    print_info(f"Found data file: {data_file}")
    print_info("This will identify trades with multiple confluence factors")
    print()

    try:
        result = subprocess.run([sys.executable, "analyze_confluence_zones.py"])

        if result.returncode == 0:
            print()
            print_success("Confluence analysis complete!")
            print_info("Results saved to: confluence_zones_detailed.csv")
            print()

            # Check if results file was created
            results_file = Path("confluence_zones_detailed.csv")
            if results_file.exists():
                print_info("Key findings:")
                print_info("- Trades scored by number of confluence factors (1-5)")
                print_info("- Win rates calculated for each confluence level")
                print_info("- High-value zones (3+ factors) identified")
                print()

        return result.returncode == 0
    except Exception as e:
        print_error(f"Confluence analysis failed: {e}")
        return False


def analyze_recovery_strategies():
    """Deep dive analysis of recovery strategies"""
    print_header("DEEP DIVE: RECOVERY STRATEGY ANALYSIS")
    print_info("Comprehensive investigation of:")
    print_info("  • Grid trading patterns and spacing")
    print_info("  • Hedging ratios and trigger points")
    print_info("  • DCA/Martingale lot progressions")
    print_info("  • Timing patterns (best hours/days)")
    print_info("  • Leverage and risk exposure")
    print_info("  • Combined strategy effectiveness")
    print()

    # Check if database exists
    db_file = Path("data/trading_data.db")
    if not db_file.exists():
        print_error("No trade database found!")
        print_info("Please run 'Analyze My EA' first to collect trade data")
        print()
        return False

    try:
        result = subprocess.run([sys.executable, "analyze_recovery_strategies.py"])

        if result.returncode == 0:
            print()
            print_success("Recovery strategy analysis complete!")
            print_info("Results saved to: recovery_strategy_analysis.json")
            print()

        return result.returncode == 0
    except Exception as e:
        print_error(f"Recovery analysis failed: {e}")
        return False


def generate_strategy_report():
    """Generate comprehensive strategy report and Python implementation"""
    print_header("STRATEGY REPORT GENERATOR")
    print_info("Synthesizing all analysis data into comprehensive report...")
    print_info("This will generate:")
    print_info("  • Executive summary of EA performance")
    print_info("  • Core strategy analysis (entry signals)")
    print_info("  • HTF institutional levels being used")
    print_info("  • Recovery mechanism details")
    print_info("  • Key insights and recommendations")
    print_info("  • Python implementation code template")
    print()

    # Check if required analysis files exist
    required_files = {
        "ea_reverse_engineering_detailed.csv": "EA Trade Data",
        "multi_timeframe_analysis.json": "Multi-Timeframe Analysis",
        "confluence_zones_detailed.csv": "Confluence Analysis",
        "recovery_strategy_analysis.json": "Recovery Strategy Analysis"
    }

    missing_files = []
    for file_name, description in required_files.items():
        if not Path(file_name).exists():
            missing_files.append(description)

    if missing_files:
        print_error("Missing required analysis data!")
        print_info("Please run these analyses first:")
        for missing in missing_files:
            print_info(f"  • {missing}")
        print()
        return False

    print_success("All required data files found!")
    print()

    try:
        result = subprocess.run([sys.executable, "generate_strategy_report.py"])

        if result.returncode == 0:
            print()
            print_success("Strategy report generated successfully!")
            print()
            print_info("Generated files:")
            print_info("  • ea_strategy_report.json (Summary data)")
            print_info("  • ea_python_implementation.py (Python code template)")
            print()
            print_info("The report has been displayed above.")
            print_info("Use the Python template as a starting point for your new bot!")
            print()

        return result.returncode == 0
    except Exception as e:
        print_error(f"Report generation failed: {e}")
        return False

def main():
    """Main entry point"""
    os.chdir(Path(__file__).parent)

    print_header("EA ANALYSIS - ONE CLICK SETUP")
    print_info("Reverse engineer and improve your trading EAs!")
    print()

    # Step 1: Check Python
    if not check_python_version():
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Step 2: Install dependencies if needed
    if not check_dependencies():
        if not install_dependencies():
            print_error("Setup failed - please install dependencies manually")
            input("\nPress Enter to exit...")
            sys.exit(1)

    # Step 3: Check MT5 credentials
    has_credentials = check_mt5_credentials()

    # Main loop
    while True:
        print()

        # If no credentials, prompt to set up
        if not has_credentials:
            print_info("First time setup - let's configure your MT5 credentials")
            input("\nPress Enter to continue...")
            if setup_mt5_credentials():
                has_credentials = True
            else:
                print_error("Failed to setup MT5 credentials")
                input("\nPress Enter to exit...")
                sys.exit(1)

        # Show menu
        choice = show_menu()

        if choice == '1':
            run_ea_analysis()
            input("\nPress Enter to continue...")

        elif choice == '2':
            analyze_confluence_zones()
            input("\nPress Enter to continue...")

        elif choice == '3':
            analyze_recovery_strategies()
            input("\nPress Enter to continue...")

        elif choice == '4':
            generate_strategy_report()
            input("\nPress Enter to continue...")

        elif choice == '5':
            test_mt5_connection()
            input("\nPress Enter to continue...")

        elif choice == '6':
            analyze_symbol()
            input("\nPress Enter to continue...")

        elif choice == '7':
            setup_mt5_credentials()
            has_credentials = True

        elif choice == '8':
            print()
            print_success("Thanks for using EA Analysis!")
            print()
            sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n" + Colors.YELLOW + "Cancelled by user" + Colors.END)
        sys.exit(0)
    except Exception as e:
        print_error(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)
