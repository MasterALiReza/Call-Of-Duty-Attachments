# Ox-Loadout Web Panel PowerShell Launcher
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  🚀 Ox-Loadout Web Administration Panel Launcher" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

$BackendProcess = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", ".\venv\Scripts\python.exe web\backend\run.py" -PassThru
Write-Host "✅ FastAPI Backend launched on http://localhost:8005 (PID: $($BackendProcess.Id))" -ForegroundColor Green

$FrontendProcess = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "Set-Location web\frontend; npm run dev" -PassThru
Write-Host "✅ React Vite Frontend launched on http://localhost:3000 (PID: $($FrontendProcess.Id))" -ForegroundColor Green

Write-Host ""
Write-Host "🌐 Access Panel: http://localhost:3000" -ForegroundColor Yellow
Write-Host "📚 API Swagger Docs: http://localhost:8005/docs" -ForegroundColor Yellow
