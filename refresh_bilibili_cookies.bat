@echo off
setlocal

set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"
set "PYTHON=%APP_DIR%\.venv\Scripts\python.exe"

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

echo Refreshing Bilibili cookies from Edge...
echo If this fails, close Edge fully and make sure Bilibili is logged in.
echo.

"%PYTHON%" tools\refresh_bilibili_cookies.py --browser edge

echo.
pause
