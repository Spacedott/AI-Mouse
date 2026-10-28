<#
.SYNOPSIS
  Launch the full Mouse-AI live demo on this Windows PC.

.DESCRIPTION
  Starts the read API, capture agent and live overlay, each in its own console
  window. Opens the presentation page in your default browser and a practice
  document in Word. The demo uses data\demo.db, never your real data\mouse_ai.db.

  Stop everything with demo\Stop-Demo.cmd.

.PARAMETER Fresh   Start with an empty demo store (no sample history).
.PARAMETER Keep    Keep the existing demo store; add this run as a new session.
.PARAMETER NoOverlay  Don't start the on-screen heatmap overlay.
.PARAMETER NoWord  Don't open the Word practice document.
#>
param(
    [switch]$Fresh,
    [switch]$Keep,
    [switch]$NoOverlay,
    [switch]$NoWord
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Data = Join-Path $Root 'data'
$Db = Join-Path $Data 'demo.db'
$PidFile = Join-Path $Data 'demo-pids.txt'
# PySide6 6.12 provides native Windows ARM64 and x64 wheels.
$OsArchitecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
$Py = if ($OsArchitecture -eq 'Arm64') {
    'cpython-3.12-windows-aarch64-none'
} else {
    'cpython-3.12-windows-x86_64-none'
}
$ApiUrl = 'http://127.0.0.1:8000'

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host 'uv is required. Install it, then re-run:' -ForegroundColor Red
    Write-Host '  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    exit 1
}

# Close any previous demo first so ports and the overlay aren't doubled up.
& (Join-Path $PSScriptRoot 'stop-demo.ps1') -Quiet

if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host 'Port 8000 is already in use (another API or docker compose?). Stop it and retry.' -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $Data | Out-Null

function UvRun([string]$Requirements) {
    $a = @('run', '--no-project', '--python', $Py)
    if ($Requirements) { $a += @('--with-requirements', $Requirements) }
    return $a + 'python'
}

Step 'Preparing Python environments (the first run downloads packages and takes a few minutes)'
$envs = @(@("$Root\api\requirements.txt", 'import fastapi, uvicorn, reportlab'),
          @("$Root\agent\requirements.txt", 'import pynput'))
if (-not $NoOverlay) { $envs += ,@("$Root\overlay\requirements.txt", 'import PySide6, pynput') }
foreach ($e in $envs) {
    & uv @(UvRun $e[0]) -c $e[1]
    if ($LASTEXITCODE -ne 0) { Write-Host "Environment setup failed for $($e[0])." -ForegroundColor Red; exit 1 }
}

Step 'Preparing the demo click store'
$seedArgs = @()
if ($Fresh) { $seedArgs = @('--reset', '--empty') } elseif (-not $Keep) { $seedArgs = @('--reset') }
$env:MOUSE_AI_DB = $Db
& uv @(UvRun '') "$PSScriptRoot\seed_demo.py" --db $Db @seedArgs
if ($LASTEXITCODE -ne 0) { exit 1 }

# Each component gets its own console window (visible logs, Ctrl+C to stop it).
$pids = @()
function Launch([string]$Title, [string]$Dir, [string]$Command) {
    $quotedDb = $Db.Replace("'", "''")
    $quotedDir = $Dir.Replace("'", "''")
    $script = "`$host.UI.RawUI.WindowTitle = 'Mouse-AI: $Title'; " +
              "`$env:MOUSE_AI_DB = '$quotedDb'; Set-Location '$quotedDir'; $Command"
    $p = Start-Process powershell -PassThru -WorkingDirectory $Dir `
        -ArgumentList @('-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass', '-Command', $script)
    $script:pids += $p.Id
    Set-Content -Path $PidFile -Value $script:pids
}
$uvPrefix = "uv run --no-project --python $Py --with-requirements requirements.txt python"

Step 'Starting the read API on port 8000'
Launch 'API' "$Root\api" "$uvPrefix -m uvicorn mouse_ai_api.main:app --host 127.0.0.1 --port 8000"
$deadline = (Get-Date).AddSeconds(60)
do {
    Start-Sleep -Milliseconds 500
    try { Invoke-WebRequest "$ApiUrl/api/sessions" -UseBasicParsing -TimeoutSec 2 | Out-Null; $up = $true }
    catch { $up = $false }
} until ($up -or (Get-Date) -gt $deadline)
if (-not $up) { Write-Host 'The API did not start; check its window.' -ForegroundColor Red; exit 1 }

Step 'Starting the capture agent'
Launch 'Capture agent' "$Root\agent" "$uvPrefix -m mouse_ai_agent.main"

if (-not $NoOverlay) {
    Step 'Starting the live overlay (press Esc to hide it)'
    Launch 'Overlay' "$Root\overlay" "$uvPrefix -m mouse_ai_overlay.main"
}

Step 'Opening the presentation page'
Start-Process (Join-Path $PSScriptRoot 'index.html')

if (-not $NoWord) {
    Step 'Opening the Word practice document'
    # Work on a copy so the demo edits never touch the checked-in file.
    $doc = Join-Path $Data 'Mouse-AI-Practice.docx'
    try {
        Copy-Item (Join-Path $PSScriptRoot 'Mouse-AI-Practice.docx') $doc -Force
        Start-Process $doc
    } catch {
        Write-Host "Couldn't open Word: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

Write-Host "`nMouse-AI demo is running." -ForegroundColor Green
Write-Host "  Presentation page : $PSScriptRoot\index.html"
Write-Host "  API               : $ApiUrl/docs"
Write-Host "  Demo store        : $Db"
Write-Host "  Stop everything   : demo\Stop-Demo.cmd"
