@echo off
setlocal
cd /d E:\Invest\FigureLearning
echo [知识酷] 正在关闭旧的 8000 端口后端...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue; foreach ($p in $ports) { try { Stop-Process -Id $p.OwningProcess -Force -ErrorAction Stop } catch {} }"
echo [知识酷] 正在启动当前后端代码...
start "知识酷后端" /min ".\.venv\Scripts\python.exe" "run_server.py"
echo [知识酷] 已发送启动命令。请等待 3-5 秒后刷新网页。
timeout /t 5 /nobreak >nul
endlocal
