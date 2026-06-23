@echo off
setlocal

set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"
if "%BILIBILI_COOKIE_EXPORT_URL%"=="" set "BILIBILI_COOKIE_EXPORT_URL=https://space.bilibili.com/520819684"

cd /d "%APP_DIR%"
if errorlevel 1 (
  echo Cannot enter project directory:
  echo %APP_DIR%
  pause
  exit /b 1
)

if not exist "%APP_DIR%\frontend\workbench\node_modules" (
  echo Node dependencies for frontend are missing.
  echo This helper is mainly for a dev machine with Node and Playwright installed.
  pause
  exit /b 1
)

echo Opening Edge to export Bilibili cookies...
echo Cookies will be saved to auth\bilibili.cookies.txt.
echo.

pushd "%APP_DIR%\frontend\workbench"
call npm.cmd exec playwright --version >nul 2>nul
if errorlevel 1 (
  popd
  echo Playwright command is not available.
  echo Install frontend Node dependencies first.
  pause
  exit /b 1
)

call npm.cmd exec node "%APP_DIR%\tools\export_bilibili_cookies_with_playwright.js" "%BILIBILI_COOKIE_EXPORT_URL%"
popd

echo.
pause
