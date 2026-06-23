@echo off
setlocal

set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"
set "PYTHON=%APP_DIR%\.venv\Scripts\python.exe"
set "URL=http://127.0.0.1:8000"
set "FIGURELEARNING_DEPLOYMENT_MODE=local"
set "FIGURELEARNING_SESSION_COOKIE_SECURE="
set "FIGURELEARNING_YTDLP_COOKIES_FILE=%APP_DIR%\auth\bilibili.cookies.txt"
set "FIGURELEARNING_YTDLP_COOKIES_FROM_BROWSER="

title ZhiShiKu Local

cd /d "%APP_DIR%"
if errorlevel 1 (
  echo Cannot enter project directory:
  echo %APP_DIR%
  pause
  exit /b 1
)

if not exist "%PYTHON%" (
  echo First-run setup is incomplete.
  echo Please run "瀹夎鐭ヨ瘑閰?棣栨杩愯.bat" first.
  pause
  exit /b 1
)

echo Stopping old service on port 8000...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue; foreach ($p in $ports) { try { Stop-Process -Id $p.OwningProcess -Force -ErrorAction Stop } catch {} }"

echo Starting ZhiShiKu in local mode from:
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
