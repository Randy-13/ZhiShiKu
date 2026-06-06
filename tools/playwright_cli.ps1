$ErrorActionPreference = "Stop"

$runtimeRoot = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node"
$nodeExe = Join-Path $runtimeRoot "bin\node.exe"
$nodeModules = Join-Path $runtimeRoot "node_modules"
$pnpmModules = Join-Path $nodeModules ".pnpm\node_modules"
$playwrightCli = Join-Path $nodeModules "playwright\cli.js"

if (-not (Test-Path -LiteralPath $nodeExe)) {
  throw "Bundled Node.js was not found: $nodeExe"
}
if (-not (Test-Path -LiteralPath $playwrightCli)) {
  throw "Bundled Playwright CLI was not found: $playwrightCli"
}

$env:NODE_PATH = "$nodeModules;$pnpmModules"

$finalArgs = @()
$commandWithChannel = @("open", "codegen", "cr", "screenshot", "pdf")
$channel = $env:PLAYWRIGHT_CHANNEL
if ($channel) {
  $commandName = $null
  foreach ($arg in $args) {
    if ($arg -and -not $arg.StartsWith("-")) {
      $commandName = $arg
      break
    }
  }
  $hasChannel = $false
  foreach ($arg in $args) {
    if ($arg -eq "--channel" -or $arg.StartsWith("--channel=")) {
      $hasChannel = $true
      break
    }
  }
  if ($commandName -and $commandWithChannel -contains $commandName -and -not $hasChannel) {
    foreach ($arg in $args) {
      $finalArgs += $arg
      if ($arg -eq $commandName) {
        $finalArgs += "--channel"
        $finalArgs += $channel
      }
    }
  } else {
    $finalArgs = $args
  }
} else {
  $finalArgs = $args
}

& $nodeExe $playwrightCli @finalArgs
exit $LASTEXITCODE
