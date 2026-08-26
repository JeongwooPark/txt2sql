# 맵 UI 골드 — Chromium 창에서 챗 입력/답변을 눈으로 확인
# Usage:
#   powershell -File tests/map_ui_gold500/run_watch.ps1
#   powershell -File tests/map_ui_gold500/run_watch.ps1 -Limit 5
param(
    [int]$Limit = 0,
    [string]$Ids = "",
    [string]$Questions = "docs/llm2sql_신규_자연어질의_테스트셋_500건_정답표.json"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
chcp 65001 | Out-Null
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root

$argsList = @(
    "run", "python", "-m", "tests.map_ui_gold500.run",
    "--watch",
    "--start-server",
    "--questions", $Questions
)
if ($Limit -gt 0) { $argsList += @("--limit", "$Limit") }
if ($Ids) { $argsList += @("--ids", $Ids) }

Write-Host ">>> uv $($argsList -join ' ')" -ForegroundColor Cyan
& uv @argsList
exit $LASTEXITCODE
