# Check which Python command works
Write-Host "Checking Python installation..." -ForegroundColor Cyan

if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "✅ 'python' found:" -ForegroundColor Green
    python --version
    $pythonCmd = "python"
}
elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    Write-Host "✅ 'python3' found:" -ForegroundColor Green
    python3 --version
    $pythonCmd = "python3"
}
elseif (Get-Command py -ErrorAction SilentlyContinue) {
    Write-Host "✅ 'py' found:" -ForegroundColor Green
    py --version
    $pythonCmd = "py"
}
else {
    Write-Host "❌ Python not found in PATH" -ForegroundColor Red
    Write-Host "`nPlease install Python or add it to your PATH" -ForegroundColor Yellow
    exit
}

Write-Host "`nUse '$pythonCmd' to run Python commands" -ForegroundColor Yellow
