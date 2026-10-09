@echo off
chcp 65001 > nul
echo ===================================================
echo   🚀 Ox-Loadout Web Administration Panel Launcher
echo ===================================================
echo.

echo [1/2] Starting FastAPI Backend on http://localhost:8005 ...
start "Ox-Loadout Backend" cmd /k ".\venv\Scripts\python.exe web\backend\run.py"

echo [2/2] Starting React Vite Frontend on http://localhost:3000 ...
start "Ox-Loadout Frontend" cmd /k "cd web\frontend && npm run dev"

echo.
echo ✅ Web Panel is starting up!
echo 🌐 Open your browser at: http://localhost:3000
echo 📚 OpenAPI Swagger Docs at: http://localhost:8005/docs
echo.
pause
