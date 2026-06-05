@echo off
setlocal

set "APP_DIR=E:\Invest\FigureLearning"
set "PYTHON=%APP_DIR%\.venv\Scripts\python.exe"
set "URL=http://127.0.0.1:8000"

title FigureLearning Screenshot Knowledge Base

cd /d "%APP_DIR%"
if errorlevel 1 (
  echo Cannot enter app directory: %APP_DIR%
  pause
  exit /b 1
)

if not exist "%PYTHON%" (
  echo Python virtual environment was not found:
  echo %PYTHON%
  echo.
  echo Please run dependency installation first.
  pause
  exit /b 1
)

echo Starting FigureLearning...
echo Browser URL: %URL%
echo.
echo Keep this window open while using the app.
echo Press Ctrl+C in this window to stop the server.
echo.

start "" "%URL%"
"%PYTHON%" run_server.py

echo.
echo Server stopped.
pause
