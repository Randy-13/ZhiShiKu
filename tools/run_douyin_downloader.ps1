param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]] $ArgsList
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pythonEnv = Join-Path $root ".venv\Scripts"
$downloader = Join-Path $pythonEnv "douyin-dl.exe"
$config = Join-Path $root "auth\douyin_downloader.config.yml"
$authDir = Join-Path $root "auth"
$downloadDir = Join-Path $root "media\douyin_downloads"
$netscapeCookies = Join-Path $authDir "douyin.cookies.txt"
$jsonCookies = Join-Path $authDir ".cookies.json"

if (-not (Test-Path -LiteralPath $downloader)) {
  throw "douyin-dl.exe was not found. Install douyin-downloader in .venv first."
}

if (-not (Test-Path -LiteralPath $config)) {
  throw "Config file was not found: $config"
}

New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null

$jsonCookiesNeedsRefresh = $true
if (Test-Path -LiteralPath $jsonCookies) {
  try {
    $existingCookies = Get-Content -LiteralPath $jsonCookies -Raw -Encoding UTF8 | ConvertFrom-Json
    $existingCookieCount = if ($null -eq $existingCookies) { 0 } else { @($existingCookies.PSObject.Properties).Count }
    $jsonCookiesNeedsRefresh = $existingCookieCount -eq 0
  } catch {
    $jsonCookiesNeedsRefresh = $true
  }
}

if ((Test-Path -LiteralPath $netscapeCookies) -and $jsonCookiesNeedsRefresh) {
  $cookies = [ordered]@{}
  Get-Content -LiteralPath $netscapeCookies -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#")) {
      $parts = $line -split "`t"
      if ($parts.Count -ge 7 -and $parts[0] -match "douyin\.com|iesdouyin\.com|bytedance\.com") {
        $cookies[$parts[5]] = $parts[6]
      }
    }
  }
  if ($cookies.Count -gt 0) {
    $cookies | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $jsonCookies -Encoding UTF8
  }
}

if (Test-Path -LiteralPath $netscapeCookies) {
  $cookiePairs = New-Object System.Collections.Generic.List[string]
  Get-Content -LiteralPath $netscapeCookies -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#")) {
      $parts = $line -split "`t"
      if ($parts.Count -ge 7 -and $parts[0] -match "douyin\.com|iesdouyin\.com|bytedance\.com") {
        $cookiePairs.Add("$($parts[5])=$($parts[6])")
      }
    }
  }
  if ($cookiePairs.Count -gt 0) {
    $env:DOUYIN_COOKIE = [string]::Join("; ", $cookiePairs)
  }
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:TERM = "xterm"

Push-Location $authDir
try {
  & $downloader -c $config @ArgsList
} finally {
  Pop-Location
}
