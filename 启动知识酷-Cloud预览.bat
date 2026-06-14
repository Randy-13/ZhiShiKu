@echo off
setlocal

set "APP_DIR=E:\Invest\FigureLearning"
set "PYTHON=%APP_DIR%\.venv\Scripts\python.exe"
set "URL=http://127.0.0.1:8000"
set "FIGURELEARNING_DEPLOYMENT_MODE=cloud"
set "FIGURELEARNING_SESSION_COOKIE_SECURE=false"
set "FIGURELEARNING_YTDLP_COOKIES_FILE=%APP_DIR%\auth\bilibili.cookies.txt"
set "FIGURELEARNING_YTDLP_COOKIES_FROM_BROWSER="

set "BOOTSTRAP_EMAIL=admin@example.test"
set "BOOTSTRAP_USERNAME=admin"
set "BOOTSTRAP_PASSWORD=password-123"

title ZhiShiKu Cloud Preview

cd /d "%APP_DIR%"
if errorlevel 1 (
  echo Cannot enter app directory: %APP_DIR%
  pause
  exit /b 1
)

if not exist "%PYTHON%" (
  echo Python virtual environment was not found:
  echo %PYTHON%
  pause
  exit /b 1
)

echo Bootstrapping cloud preview admin and invite code...
"%PYTHON%" tools\bootstrap_cloud_auth.py --email "%BOOTSTRAP_EMAIL%" --username "%BOOTSTRAP_USERNAME%" --password "%BOOTSTRAP_PASSWORD%"
if errorlevel 1 (
  echo Cloud auth bootstrap failed.
  pause
  exit /b 1
)

echo.
echo Cloud preview login:
echo   email:    %BOOTSTRAP_EMAIL%
echo   username: %BOOTSTRAP_USERNAME%
echo   password: %BOOTSTRAP_PASSWORD%
echo.
echo Stopping any old backend on port 8000...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue; foreach ($p in $ports) { try { Stop-Process -Id $p.OwningProcess -Force -ErrorAction Stop } catch {} }"

echo Starting ZhiShiKu in cloud preview mode from:
echo %APP_DIR%
echo.
echo Browser URL: %URL%
echo Keep this window open while using the app.
echo Press Ctrl+C to stop the server.
echo.

start "" powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 3; Start-Process '%URL%'"
"%PYTHON%" run_server.py

echo.
echo Server stopped.
pause
