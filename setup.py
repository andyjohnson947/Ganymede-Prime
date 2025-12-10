#!/usr/bin/env python3
"""
MT5 Trading Bot - One-Click Setup Script
Automatically sets up the environment and configures the bot
"""

import os
import sys
import subprocess
import platform
from pathlib import Path


def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def print_step(step_num, text):
    """Print step information"""
    print(f"\n[{step_num}] {text}...")


def check_python_version():
    """Check if Python version is adequate"""
    print_step(1, "Checking Python version")

    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python 3.8+ required. You have Python {version.major}.{version.minor}")
        sys.exit(1)

    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")


def create_virtual_environment():
    """Create virtual environment"""
    print_step(2, "Creating virtual environment")

    venv_path = Path("venv")

    if venv_path.exists():
        print("⚠️  Virtual environment already exists, skipping...")
        return True

    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✅ Virtual environment created")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create virtual environment: {e}")
        return False


def get_pip_command():
    """Get the correct pip command based on OS"""
    if platform.system() == "Windows":
        return str(Path("venv/Scripts/pip.exe"))
    else:
        return str(Path("venv/bin/pip"))


def get_python_command():
    """Get the correct python command based on OS"""
    if platform.system() == "Windows":
        return str(Path("venv/Scripts/python.exe"))
    else:
        return str(Path("venv/bin/python"))


def install_dependencies():
    """Install required dependencies"""
    print_step(3, "Installing dependencies")

    pip_cmd = get_pip_command()

    # Upgrade pip first
    print("  Upgrading pip...")
    try:
        subprocess.run([pip_cmd, "install", "--upgrade", "pip"], check=True,
                      stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        print("  ⚠️  Pip upgrade failed, continuing anyway...")

    # Install requirements
    print("  Installing packages (this may take a few minutes)...")
    try:
        result = subprocess.run(
            [pip_cmd, "install", "-r", "requirements.txt"],
            check=True,
            capture_output=True,
            text=True
        )
        print("✅ Dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies")
        print(f"Error: {e.stderr}")
        return False


def create_directories():
    """Create necessary directories"""
    print_step(4, "Creating directories")

    directories = ["data", "logs", "models"]

    for directory in directories:
        path = Path(directory)
        path.mkdir(exist_ok=True)
        print(f"  ✅ {directory}/")

    print("✅ Directories created")


def setup_configuration():
    """Setup configuration files"""
    print_step(5, "Setting up configuration")

    cred_file = Path("config/mt5_credentials.yaml")

    if cred_file.exists():
        print("  ⚠️  MT5 credentials file already exists")
        print("  To reconfigure, delete config/mt5_credentials.yaml")
        return True

    print("\n  MT5 credentials not configured.")
    print("  You have two options:")
    print("\n  Option 1: Use the GUI (Recommended)")
    print("    Run: python run.py --setup")
    print("\n  Option 2: Manual configuration")
    print("    Copy: config/mt5_credentials.example.yaml")
    print("    To:   config/mt5_credentials.yaml")
    print("    Then edit with your MT5 credentials")

    return True


def create_launcher_scripts():
    """Create launcher scripts"""
    print_step(6, "Creating launcher scripts")

    # Windows batch file
    windows_launcher = """@echo off
echo Starting MT5 Trading Bot...
call venv\\Scripts\\activate.bat
python run.py %*
pause
"""

    with open("START_BOT.bat", "w") as f:
        f.write(windows_launcher)

    print("  ✅ START_BOT.bat (Windows)")

    # Linux/Mac shell script
    unix_launcher = """#!/bin/bash
echo "Starting MT5 Trading Bot..."
source venv/bin/activate
python run.py "$@"
"""

    with open("START_BOT.sh", "w") as f:
        f.write(unix_launcher)

    # Make executable on Unix
    if platform.system() != "Windows":
        os.chmod("START_BOT.sh", 0o755)

    print("  ✅ START_BOT.sh (Linux/Mac)")

    print("\n✅ Launcher scripts created")


def print_next_steps():
    """Print next steps for the user"""
    print_header("Setup Complete!")

    print("🎉 Your MT5 Trading Bot is ready to use!\n")

    print("Next Steps:")
    print("\n1. Configure MT5 Credentials:")

    if platform.system() == "Windows":
        print("   Double-click: START_BOT.bat")
        print("   Then run with: --setup flag")
    else:
        print("   Run: ./START_BOT.sh --setup")

    print("\n2. Start the Bot:")
    if platform.system() == "Windows":
        print("   Double-click: START_BOT.bat")
    else:
        print("   Run: ./START_BOT.sh")

    print("\n3. Other Commands:")
    print("   Analyze symbol:    START_BOT --analyze EURUSD")
    print("   Train ML models:   START_BOT --train")
    print("   ML predictions:    START_BOT --predict")
    print("   DCA example:       START_BOT --dca-demo")

    print("\n📖 Documentation:")
    print("   Quick Start: INSTALL.md")
    print("   Full Guide:  README.md")

    print("\n" + "=" * 60)


def main():
    """Main setup function"""
    print_header("MT5 Trading Bot - Automated Setup")

    print("This script will:")
    print("  • Check Python version")
    print("  • Create virtual environment")
    print("  • Install all dependencies")
    print("  • Create necessary directories")
    print("  • Set up launcher scripts")

    input("\nPress Enter to continue...")

    # Run setup steps
    check_python_version()

    if not create_virtual_environment():
        sys.exit(1)

    if not install_dependencies():
        sys.exit(1)

    create_directories()
    setup_configuration()
    create_launcher_scripts()

    # Success
    print_next_steps()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Setup failed: {e}")
        sys.exit(1)
