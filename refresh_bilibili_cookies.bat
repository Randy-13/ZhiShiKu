@echo off
setlocal
chcp 65001 >nul

set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"
set "PYTHON=%APP_DIR%\.venv\Scripts\python.exe"

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

echo 正在尝试从 Edge 刷新 B 站 Cookie...
echo 如果失败，请先彻底关闭 Edge，并确认已登录 B 站后再重试。
echo.

"%PYTHON%" tools\refresh_bilibili_cookies.py --browser edge

echo.
pause
