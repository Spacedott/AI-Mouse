<#
.SYNOPSIS
  Stop everything start-demo.ps1 launched (API, agent, overlay windows).
  Word and the browser are left open.
#>
param([switch]$Quiet)

$PidFile = Join-Path (Split-Path -Parent $PSScriptRoot) 'data\demo-pids.txt'
if (-not (Test-Path $PidFile)) {
    if (-not $Quiet) { Write-Host 'No Mouse-AI demo is running.' }
    exit 0
}

foreach ($id in Get-Content $PidFile) {
    if ($id -match '^\d+$') {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $id"
        # A stale PID may have been reused after the previous demo ended.
        if (-not $process -or $process.CommandLine -notlike '*Mouse-AI:*') { continue }
        # /T takes down the whole tree: console -> uv -> python.
        taskkill /PID $id /T /F | Out-Null
    }
}
Remove-Item $PidFile -Force
if (-not $Quiet) { Write-Host 'Mouse-AI demo stopped.' -ForegroundColor Green }
