# 🚀 Quick Install Guide

## One-Click Installation

### Step 1: Run Setup

**Windows:**
```bash
python setup.py
```

**Linux/Mac:**
```bash
python3 setup.py
```

This will automatically:
- ✅ Check Python version
- ✅ Create virtual environment
- ✅ Install all dependencies
- ✅ Create necessary directories
- ✅ Generate launcher scripts

### Step 2: Configure MT5 Credentials

**Windows:**
```bash
START_BOT.bat --setup
```

**Linux/Mac:**
```bash
./START_BOT.sh --setup
```

Or run directly:
```bash
python run.py --setup
```

A GUI window will open:
1. Enter your MT5 login number
2. Enter your password
3. Enter your broker server (e.g., "YourBroker-Demo")
4. Click "Test Connection" to verify
5. Click "Save Configuration"

### Step 3: Start the Bot

**Windows:**
- Double-click `START_BOT.bat`

**Linux/Mac:**
```bash
./START_BOT.sh
```

Or run directly:
```bash
python run.py
```

That's it! 🎉

---

## Quick Commands

All commands work with either the launcher scripts or directly with `python run.py`:

| Task | Command |
|------|---------|
| **Start Bot** | `START_BOT` or `python run.py` |
| **Setup Credentials** | `START_BOT --setup` |
| **Analyze Symbol** | `START_BOT --analyze EURUSD` |
| **Train ML Models** | `START_BOT --train` |
| **ML Predictions** | `START_BOT --predict` |
| **DCA Demo** | `START_BOT --dca-demo` |
| **Collect Data** | `START_BOT --collect` |

---

## Alternative: Manual Setup

If the automated setup doesn't work:

### 1. Install Python 3.8+
Download from: https://www.python.org/downloads/

### 2. Create Virtual Environment
```bash
python -m venv venv
```

### 3. Activate Virtual Environment

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure MT5
Copy `config/mt5_credentials.example.yaml` to `config/mt5_credentials.yaml` and edit with your credentials.

### 6. Run
```bash
python run.py
```

---

## Troubleshooting

### "Python not found"
- Install Python 3.8 or higher
- Make sure Python is in your PATH

### "pip: command not found"
```bash
python -m pip install --upgrade pip
```

### "Module not found"
```bash
pip install -r requirements.txt
```

### "Failed to connect to MT5"
- Make sure MT5 is installed and running
- Check your credentials in `config/mt5_credentials.yaml`
- Verify your broker server name

### Dependencies fail to install
Some packages might need additional system libraries:

**Windows:**
- Install Visual C++ Redistributable

**Linux:**
```bash
sudo apt-get install python3-dev build-essential
```

**Mac:**
```bash
xcode-select --install
```

---

## What Gets Installed

The setup installs these main packages:
- **MetaTrader5**: MT5 API integration
- **pandas & numpy**: Data processing
- **scikit-learn**: Machine learning
- **scipy & statsmodels**: Statistical analysis
- **TA-Lib**: Technical analysis (requires separate system installation)
- **PyYAML**: Configuration management
- **schedule**: Task scheduling

---

## Next Steps

After installation:

1. **Test the connection:**
   ```bash
   python run.py --analyze EURUSD
   ```

2. **Collect initial data:**
   ```bash
   python run.py --collect
   ```

3. **Train ML models:**
   ```bash
   python run.py --train
   ```

4. **Start trading:**
   ```bash
   python run.py
   ```

---

## Support

- 📖 Full documentation: `README.md`
- 💡 Examples: Check the `examples/` folder
- 🐛 Issues: Report problems on GitHub

Enjoy trading! 🚀📈
