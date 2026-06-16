@echo off
setlocal
chcp 65001 >nul

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

title 知识酷 Cloud 预览

cd /d "%APP_DIR%"
if errorlevel 1 (
  echo 无法进入项目目录：
  echo %APP_DIR%
  pause
  exit /b 1
)

if not exist "%PYTHON%" (
  echo 尚未完成首次安装。
  echo 请先双击运行“安装知识酷-首次运行.bat”。
  pause
  exit /b 1
)

echo 正在初始化 cloud 预览账号...
"%PYTHON%" tools\bootstrap_cloud_auth.py --email "%BOOTSTRAP_EMAIL%" --username "%BOOTSTRAP_USERNAME%" --password "%BOOTSTRAP_PASSWORD%"
if errorlevel 1 (
  echo Cloud 预览初始化失败。
  pause
  exit /b 1
)

echo.
echo Cloud 预览登录信息：
echo   email:    %BOOTSTRAP_EMAIL%
echo   username: %BOOTSTRAP_USERNAME%
echo   password: %BOOTSTRAP_PASSWORD%
echo.
echo 正在关闭旧的 8000 端口服务...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue; foreach ($p in $ports) { try { Stop-Process -Id $p.OwningProcess -Force -ErrorAction Stop } catch {} }"

echo 正在以 cloud 预览模式启动知识酷：
echo %APP_DIR%
echo.
echo 浏览器地址：%URL%
echo 使用期间请保持此窗口开启。
echo 按 Ctrl+C 可停止服务。
echo.

start "" powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 3; Start-Process '%URL%'"
"%PYTHON%" run_server.py

echo.
echo 服务已停止。
pause
