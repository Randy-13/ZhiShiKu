@echo off
setlocal

set "APP_DIR=E:\Invest\FigureLearning"
set "NODE=C:\Users\Bo Yang\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
set "NODE_MODULES=C:\Users\Bo Yang\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules"
set "NODE_PATH=%NODE_MODULES%;%NODE_MODULES%\.pnpm\node_modules"
if "%BILIBILI_COOKIE_EXPORT_URL%"=="" set "BILIBILI_COOKIE_EXPORT_URL=https://space.bilibili.com/520819684"

cd /d "%APP_DIR%"
if errorlevel 1 (
  echo Cannot enter app directory: %APP_DIR%
  pause
  exit /b 1
)

echo Opening Edge for Bilibili cookie export...
echo If Bilibili is not logged in, log in inside the opened Edge window.
echo This tool will save cookies to auth\bilibili.cookies.txt without printing secret values.
echo.

"%NODE%" tools\export_bilibili_cookies_with_playwright.js "%BILIBILI_COOKIE_EXPORT_URL%"

echo.
pause
