@echo off
setlocal
chcp 65001 >nul

set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"
if "%BILIBILI_COOKIE_EXPORT_URL%"=="" set "BILIBILI_COOKIE_EXPORT_URL=https://space.bilibili.com/520819684"

cd /d "%APP_DIR%"
if errorlevel 1 (
  echo 无法进入项目目录：
  echo %APP_DIR%
  pause
  exit /b 1
)

if not exist "%APP_DIR%\frontend\workbench\node_modules" (
  echo 未检测到本项目前端 Node 依赖目录。
  echo 这个脚本更适合开发环境或已经装好 Node / Playwright 的环境使用。
  echo 普通用户如只需使用本地版，可先跳过这一步。
  pause
  exit /b 1
)

echo 正在打开 Edge，用于导出 B 站 Cookie...
echo 如果 B 站未登录，请在打开的窗口中先完成登录。
echo Cookie 会保存到 auth\bilibili.cookies.txt，不会直接打印敏感值。
echo.

pushd "%APP_DIR%\frontend\workbench"
call npm.cmd exec playwright --version >nul 2>nul
if errorlevel 1 (
  popd
  echo 未检测到可用的 Playwright 命令。
  echo 请先在项目前端目录安装 Node 依赖后再使用此脚本。
  pause
  exit /b 1
)

call npm.cmd exec node "%APP_DIR%\tools\export_bilibili_cookies_with_playwright.js" "%BILIBILI_COOKIE_EXPORT_URL%"
popd

echo.
pause
