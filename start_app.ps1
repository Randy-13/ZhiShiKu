$ErrorActionPreference = "Stop"
$appDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $appDir
& ".\.venv\Scripts\python.exe" "run_server.py"
