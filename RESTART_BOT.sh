#!/bin/bash
echo "🔄 Stopping any running bot instances..."
pkill -f "python.*trading_bot" 2>/dev/null
pkill -f "python.*main.py" 2>/dev/null

echo "📥 Pulling latest changes from git..."
cd /home/user/EA-Analysis
git pull origin claude/lvn-multi-timeframe-analysis-01EWgVLXhH2Bi17gMNVYU4uQ

echo "🧹 Clearing Python cache..."
find /home/user/EA-Analysis/trading_bot -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find /home/user/EA-Analysis/trading_bot -type f -name "*.pyc" -delete 2>/dev/null

echo "✅ Ready to restart!"
echo ""
echo "Current settings:"
python3 -c "import sys; sys.path.insert(0, '/home/user/EA-Analysis/trading_bot'); from config.strategy_config import BASE_LOT_SIZE, MAX_POSITIONS_PER_SYMBOL, GRID_ENABLED, HEDGE_ENABLED, DCA_ENABLED; print(f'  BASE_LOT_SIZE: {BASE_LOT_SIZE}'); print(f'  MAX_POSITIONS_PER_SYMBOL: {MAX_POSITIONS_PER_SYMBOL}'); print(f'  GRID_ENABLED: {GRID_ENABLED}'); print(f'  HEDGE_ENABLED: {HEDGE_ENABLED}'); print(f'  DCA_ENABLED: {DCA_ENABLED}')"
echo ""
echo "Now start the bot with:"
echo "  cd /home/user/EA-Analysis"
echo "  python3 -m trading_bot.main --login YOUR_LOGIN --password YOUR_PASSWORD --server YOUR_SERVER"
