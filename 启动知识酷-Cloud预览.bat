@echo off
setlocal

set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"
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

echo Bootstrapping cloud preview account...
"%PYTHON%" tools\bootstrap_cloud_auth.py --email "%BOOTSTRAP_EMAIL%" --username "%BOOTSTRAP_USERNAME%" --password "%BOOTSTRAP_PASSWORD%"
if errorlevel 1 (
  echo Cloud preview bootstrap failed.
  pause
  exit /b 1
)

echo.
echo Cloud preview login:
echo   email:    %BOOTSTRAP_EMAIL%
echo   username: %BOOTSTRAP_USERNAME%
echo   password: %BOOTSTRAP_PASSWORD%
echo.
echo Stopping old service on port 8000...
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
