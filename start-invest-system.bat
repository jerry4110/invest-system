@echo off
rem ============================================
rem  Invest-System Launcher (D-013 / Phase 1)
rem  1) Backend (FastAPI :8000)  2) Frontend (Vite :5173)  3) Browser
rem ============================================
cd /d "%~dp0"

echo [1/3] Backend starting...
start "invest-backend" cmd /k "cd /d %~dp0 && python -m uvicorn backend.main:app --port 8000 --reload"

echo [2/3] Frontend starting...
start "invest-frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo [3/3] Waiting for servers (8 sec)...
timeout /t 8 /nobreak >nul
start http://localhost:5173

echo.
echo  Done! Two server windows must stay open.
echo  To stop: close the "invest-backend" and "invest-frontend" windows.
timeout /t 5 >nul
