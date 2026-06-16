@echo off
setlocal
chcp 65001 >nul

set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"
set "VENV_PYTHON=%APP_DIR%\.venv\Scripts\python.exe"
set "ENV_FILE=%APP_DIR%\.env"
set "ENV_EXAMPLE=%APP_DIR%\.env.example"

title 知识酷 安装器

cd /d "%APP_DIR%"
if errorlevel 1 (
  echo 无法进入项目目录：
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
    echo 未检测到 Python。
    echo 请先安装 Python 3.10 或 3.11，并勾选“Add Python to PATH”。
    pause
    exit /b 1
  )
  set "PYTHON_BOOTSTRAP=python"
)

if not exist "%APP_DIR%\.venv\Scripts\python.exe" (
  echo 正在创建虚拟环境...
  call %PYTHON_BOOTSTRAP% -m venv "%APP_DIR%\.venv"
  if errorlevel 1 (
    echo 创建虚拟环境失败。
    pause
    exit /b 1
  )
)

echo 正在升级 pip...
"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 (
  echo pip 升级失败。
  pause
  exit /b 1
)

echo 正在安装后端依赖...
"%VENV_PYTHON%" -m pip install -r "%APP_DIR%\requirements.txt"
if errorlevel 1 (
  echo 依赖安装失败。
  pause
  exit /b 1
)

if not exist "%ENV_FILE%" (
  if exist "%ENV_EXAMPLE%" (
    copy /Y "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
    echo 已创建 .env，请稍后填写 API Key。
  )
)

if not exist "%APP_DIR%\knowledge" mkdir "%APP_DIR%\knowledge"
if not exist "%APP_DIR%\images" mkdir "%APP_DIR%\images"
if not exist "%APP_DIR%\documents" mkdir "%APP_DIR%\documents"
if not exist "%APP_DIR%\auth" mkdir "%APP_DIR%\auth"
if not exist "%APP_DIR%\output" mkdir "%APP_DIR%\output"

echo.
echo 安装完成。
echo 下一步：
echo 1. 打开 .env，填写你的 API Key
echo 2. 双击“启动知识酷.bat”
echo.
pause
