@echo off
setlocal

set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"
set "VENV_PYTHON=%APP_DIR%\.venv\Scripts\python.exe"
set "ENV_FILE=%APP_DIR%\.env"
set "ENV_EXAMPLE=%APP_DIR%\.env.example"

title ZhiShiKu Installer

cd /d "%APP_DIR%"
if errorlevel 1 (
  echo Cannot enter project directory:
  echo %APP_DIR%
  pause
  exit /b 1
)

where py >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_BOOTSTRAP=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python was not found.
    echo Install Python 3.10 or 3.11 and enable "Add Python to PATH".
    pause
    exit /b 1
  )
  set "PYTHON_BOOTSTRAP=python"
)

if not exist "%APP_DIR%\.venv\Scripts\python.exe" (
  echo Creating virtual environment...
  call %PYTHON_BOOTSTRAP% -m venv "%APP_DIR%\.venv"
  if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
  )
)

echo Upgrading pip...
"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 (
  echo Failed to upgrade pip.
  pause
  exit /b 1
)

echo Installing backend dependencies...
"%VENV_PYTHON%" -m pip install -r "%APP_DIR%\requirements.txt"
if errorlevel 1 (
  echo Failed to install dependencies.
  pause
  exit /b 1
)

if not exist "%ENV_FILE%" (
  if exist "%ENV_EXAMPLE%" (
    copy /Y "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
    echo Created .env. Please add your API key before first use.
  )
)

if not exist "%APP_DIR%\knowledge" mkdir "%APP_DIR%\knowledge"
if not exist "%APP_DIR%\images" mkdir "%APP_DIR%\images"
if not exist "%APP_DIR%\documents" mkdir "%APP_DIR%\documents"
if not exist "%APP_DIR%\auth" mkdir "%APP_DIR%\auth"
if not exist "%APP_DIR%\output" mkdir "%APP_DIR%\output"

echo.
echo Setup complete.
echo 1. Open .env and add your API key.
echo 2. Double-click "鍚姩鐭ヨ瘑閰?bat".
echo.
pause
