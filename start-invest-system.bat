@echo off
rem ============================================
rem  Invest-System Launcher (D-013 / D-020)
rem  Backend 준비 확인 후 Frontend·Browser 순차 기동 (proxy ECONNREFUSED 방지)
rem ============================================
cd /d "%~dp0"

echo [1/3] Backend starting...
start "invest-backend" cmd /k "cd /d %~dp0 && python -m uvicorn backend.main:app --port 8000 --reload"

echo [2/3] Waiting for backend (max 60s)...
set /a tries=0
:waitloop
curl -s -o nul -m 2 http://localhost:8000/api/health
if %errorlevel%==0 goto ready
set /a tries+=1
if %tries% geq 30 (
  echo   Backend not responding after 60s - check the invest-backend window for errors.
  goto frontend
)
timeout /t 2 /nobreak >nul
goto waitloop

:ready
echo   Backend is ready!

:frontend
echo [3/3] Frontend starting...
start "invest-frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
timeout /t 4 /nobreak >nul
start http://localhost:5173

echo.
echo  Done! Two server windows must stay open.
timeout /t 5 >nul
