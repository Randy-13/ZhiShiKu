param(
  [string]$Version = "",
  [string]$OutputRoot = "output\releases",
  [switch]$SkipBuildCheck
)

$ErrorActionPreference = "Stop"

function Ensure-Path([string]$PathValue) {
  if (-not (Test-Path -LiteralPath $PathValue)) {
    throw "Missing required path: $PathValue"
  }
}

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

$resolvedOutputRoot = Join-Path $projectRoot $OutputRoot
if (-not (Test-Path -LiteralPath $resolvedOutputRoot)) {
  New-Item -ItemType Directory -Path $resolvedOutputRoot | Out-Null
}

$releaseVersion = if ($Version.Trim()) { $Version.Trim() } else { Get-Date -Format "yyyyMMdd-HHmmss" }
$releaseName = "zhishiku-local-$releaseVersion"
$stagingRoot = Join-Path $resolvedOutputRoot $releaseName
$zipPath = Join-Path $resolvedOutputRoot "$releaseName.zip"

if (Test-Path -LiteralPath $stagingRoot) {
  Remove-Item -LiteralPath $stagingRoot -Recurse -Force
}

if (Test-Path -LiteralPath $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}

$requiredFiles = @(
  "README.md",
  ".env.example",
  "requirements.txt",
  "run_server.py",
  "app.py",
  "storage.py",
  "writer_tools.py",
  "refresh_bilibili_cookies.bat",
  "export_bilibili_cookies_with_edge.bat",
  "start_app.cmd",
  "start_app.ps1"
)

foreach ($relativePath in $requiredFiles) {
  Ensure-Path (Join-Path $projectRoot $relativePath)
}

$rootBatchFiles = Get-ChildItem -LiteralPath $projectRoot -File -Filter "*.bat"
if (-not $rootBatchFiles) {
  throw "Missing expected startup batch files in project root."
}

$frontendDist = Join-Path $projectRoot "frontend\workbench\dist\index.html"
if (-not $SkipBuildCheck) {
  Ensure-Path $frontendDist
}

New-Item -ItemType Directory -Path $stagingRoot | Out-Null

$includePaths = @(
  ".env.example",
  ".gitattributes",
  ".gitignore",
  "README.md",
  "AGENTS.md",
  "requirements.txt",
  "run_server.py",
  "app.py",
  "api_settings.py",
  "asr_settings.py",
  "config.py",
  "deepseek_client.py",
  "document_parser.py",
  "graph_core.py",
  "image_api_settings.py",
  "markdown_writer.py",
  "media_parser.py",
  "media_transcriber.py",
  "ocr_client.py",
  "schemas.py",
  "storage.py",
  "web_settings.py",
  "workbench_settings.py",
  "writer_tools.py",
  "refresh_bilibili_cookies.bat",
  "export_bilibili_cookies_with_edge.bat",
  "start_app.cmd",
  "start_app.ps1",
  "docs",
  "frontend\dist",
  "frontend\workbench\dist",
  "prompts",
  "src",
  "static",
  "tools"
)

$dynamicRootFiles = @()
$dynamicRootFiles += $rootBatchFiles | ForEach-Object { $_.Name }
$dynamicRootFiles += Get-ChildItem -LiteralPath $projectRoot -File -Filter "*.cmd" | ForEach-Object { $_.Name }
$dynamicRootFiles += Get-ChildItem -LiteralPath $projectRoot -File -Filter "*.ps1" | ForEach-Object { $_.Name }
$includePaths += $dynamicRootFiles | Sort-Object -Unique

foreach ($relativePath in $includePaths) {
  $sourcePath = Join-Path $projectRoot $relativePath
  if (-not (Test-Path -LiteralPath $sourcePath)) {
    continue
  }
  $destinationPath = Join-Path $stagingRoot $relativePath
  $parent = Split-Path -Parent $destinationPath
  if ($parent -and -not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
  }
  Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Recurse -Force
}

foreach ($dir in @("knowledge", "images", "documents", "media", "writer", "auth", "output")) {
  $targetDir = Join-Path $stagingRoot $dir
  if (-not (Test-Path -LiteralPath $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir | Out-Null
  }
  $gitkeep = Join-Path $targetDir ".gitkeep"
  if (-not (Test-Path -LiteralPath $gitkeep)) {
    New-Item -ItemType File -Path $gitkeep | Out-Null
  }
}

$notesPath = Join-Path $stagingRoot "RELEASE-NOTES.txt"
@"
知识酷 本地版
Version: $releaseVersion

Usage:
1. Run the install batch file in the project root
2. Edit .env and fill in your API key
3. Run the main start batch file in the project root
4. Open http://127.0.0.1:8000

This package intentionally excludes local databases, cookies, logs, media files, and private keys.
"@ | Set-Content -LiteralPath $notesPath -Encoding UTF8

Compress-Archive -Path (Join-Path $stagingRoot "*") -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host "Created release folder: $stagingRoot"
Write-Host "Created release zip: $zipPath"
