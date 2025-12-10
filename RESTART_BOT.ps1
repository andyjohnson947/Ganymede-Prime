# PowerShell script to restart the trading bot
Write-Host "🔄 Stopping any running bot instances..." -ForegroundColor Yellow
Get-Process python* -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -like "*trading_bot*" -or $_.CommandLine -like "*main.py*"} | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "📥 Pulling latest changes from git..." -ForegroundColor Cyan
Set-Location "C:\Users\$env:USERNAME\EA-Analysis"
git pull origin claude/lvn-multi-timeframe-analysis-01EWgVLXhH2Bi17gMNVYU4uQ

Write-Host "🧹 Clearing Python cache..." -ForegroundColor Cyan
Get-ChildItem -Path ".\trading_bot" -Filter "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path ".\trading_bot" -Filter "*.pyc" -Recurse -File | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "`n✅ Ready to restart!" -ForegroundColor Green
Write-Host "`nCurrent settings:" -ForegroundColor Yellow

python -c "import sys; sys.path.insert(0, r'C:\Users\$env:USERNAME\EA-Analysis\trading_bot'); from config.strategy_config import BASE_LOT_SIZE, MAX_POSITIONS_PER_SYMBOL, GRID_ENABLED, HEDGE_ENABLED, DCA_ENABLED; print(f'  BASE_LOT_SIZE: {BASE_LOT_SIZE}'); print(f'  MAX_POSITIONS_PER_SYMBOL: {MAX_POSITIONS_PER_SYMBOL}'); print(f'  GRID_ENABLED: {GRID_ENABLED}'); print(f'  HEDGE_ENABLED: {HEDGE_ENABLED}'); print(f'  DCA_ENABLED: {DCA_ENABLED}')"

Write-Host "`nNow start the bot with:" -ForegroundColor Yellow
Write-Host "  cd C:\Users\$env:USERNAME\EA-Analysis" -ForegroundColor White
Write-Host "  python -m trading_bot.main --login YOUR_LOGIN --password YOUR_PASSWORD --server YOUR_SERVER" -ForegroundColor White
Write-Host "`nOr just run the GUI version if you prefer." -ForegroundColor White
