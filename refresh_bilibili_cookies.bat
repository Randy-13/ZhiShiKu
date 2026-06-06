@echo off
setlocal

set "APP_DIR=E:\Invest\FigureLearning"
set "PYTHON=%APP_DIR%\.venv\Scripts\python.exe"

cd /d "%APP_DIR%"
if errorlevel 1 (
  echo Cannot enter app directory: %APP_DIR%
  pause
  exit /b 1
)

echo Refreshing Bilibili cookies from Edge...
echo If this fails, close Edge completely, make sure Bilibili is logged in, then run again.
echo.

"%PYTHON%" tools\refresh_bilibili_cookies.py --browser edge

echo.
pause
