@echo off
cd /d E:\Invest\FigureLearning\frontend\workbench
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:4173/"
npm.cmd run preview -- --host 127.0.0.1 --port 4173
