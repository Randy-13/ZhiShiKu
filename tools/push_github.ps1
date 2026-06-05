param(
  [string]$RemoteName = "origin",
  [string]$RemoteUrl = "https://github.com/Randy-13/FigureLearning.git"
)

$ErrorActionPreference = "Stop"

git rev-parse --is-inside-work-tree | Out-Null

$currentRemote = git remote get-url $RemoteName 2>$null
if (-not $currentRemote) {
  git remote add $RemoteName $RemoteUrl
} elseif ($currentRemote -ne $RemoteUrl) {
  git remote set-url $RemoteName $RemoteUrl
}

git branch -M main

git push -u $RemoteName main
git push $RemoteName legacy-web workbench-web

Write-Host "Pushed main, legacy-web, and workbench-web to $RemoteUrl"
