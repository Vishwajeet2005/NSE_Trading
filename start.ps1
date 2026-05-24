# start.ps1 — Native Windows PowerShell Startup Script for NSE Trading System
# Run:  .\start.ps1

$ErrorActionPreference = "Stop"

Write-Host "Starting NSE Trading System..." -ForegroundColor Cyan

$env:PYTHONIOENCODING = "utf-8"

# Ensure we use virtualenv binaries
$PythonPath = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$UvicornPath = Join-Path $PSScriptRoot ".venv\Scripts\uvicorn.exe"

if (-not (Test-Path $PythonPath)) {
    Write-Error "Virtual environment not found! Run setup.sh / equivalent setup steps first."
}

# Start backend (uvicorn api:app --port 8000)
Write-Host "Starting Backend API..." -ForegroundColor Yellow
$BackendProcess = Start-Process $UvicornPath -ArgumentList "backend.api.routes:app", "--port", "8000" -NoNewWindow -PassThru

# Start scanner (python main.py --mode scanner --interval 30 --no-gate)
Write-Host "Starting Scanner..." -ForegroundColor Yellow
$ScannerProcess = Start-Process $PythonPath -ArgumentList "main.py", "--mode", "scanner", "--interval", "30", "--no-gate" -NoNewWindow -PassThru

Write-Host ""
Write-Host "NSE Terminal ready!" -ForegroundColor Green
Write-Host "  Backend API : http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "  Dashboard   : Run 'python main.py --mode dashboard' in a separate terminal" -ForegroundColor Gray
Write-Host ""
Write-Host "Press Ctrl+C to stop all services..." -ForegroundColor Cyan

try {
    # Keep the script running and wait for backend to finish
    while (-not $BackendProcess.HasExited) {
        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host "`nStopping background processes..." -ForegroundColor Red
    if ($BackendProcess -and -not $BackendProcess.HasExited) {
        Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($ScannerProcess -and -not $ScannerProcess.HasExited) {
        Stop-Process -Id $ScannerProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Processes stopped." -ForegroundColor Green
}
