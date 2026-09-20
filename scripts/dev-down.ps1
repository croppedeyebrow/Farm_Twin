<#
.SYNOPSIS
  Stop FarmTwin local stack.

.DESCRIPTION
  - Stop Vite(5173) / uvicorn(8000)
  - docker compose stop db (or all with -FullCompose)

.PARAMETER FullCompose
  Stop all compose services (api/frontend/nginx/db).
#>
param(
    [switch]$FullCompose
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Stop-PortListeners([int[]]$Ports) {
    foreach ($port in $Ports) {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        foreach ($conn in $conns) {
            $procId = $conn.OwningProcess
            if (-not $procId) { continue }
            Write-Host "port $port -> stop PID $procId"
            & taskkill /F /T /PID $procId 2>$null | Out-Null
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Step "Stopping host API/Vite (8000, 5173)"
Stop-PortListeners @(8000, 5173)
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and (
            $_.CommandLine -match 'uvicorn app.main:app' -or
            $_.CommandLine -match 'vite'
        )
    } |
    ForEach-Object {
        Write-Host "stop leftover PID $($_.ProcessId)"
        & taskkill /F /T /PID $_.ProcessId 2>$null | Out-Null
    }

if ($FullCompose) {
    Write-Step "docker compose stop (all)"
    docker compose stop
}
else {
    Write-Step "docker compose stop db"
    docker compose stop db
}

Start-Sleep -Seconds 1
$left5173 = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
$left8000 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($left5173) { Write-Host "WARN: 5173 still listening" -ForegroundColor Yellow } else { Write-Host "5173 free" }
if ($left8000) { Write-Host "WARN: 8000 still listening" -ForegroundColor Yellow } else { Write-Host "8000 free" }

Write-Host ""
Write-Host "Stopped" -ForegroundColor Green