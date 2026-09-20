<#
.SYNOPSIS
  FarmTwin 로컬 개발 스택 종료.

.DESCRIPTION
  - Vite(5173) / uvicorn(8000) 프로세스 종료
  - docker compose db(및 FullCompose 시 전체) stop

.PARAMETER FullCompose
  compose 전체 서비스(api/frontend/nginx/db)를 stop 한다.
  기본은 호스트 API/Vite 종료 + db 컨테이너 stop.
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
            Write-Host "port $port → stop PID $procId"
            # 자식(uvicorn reloader worker)까지
            & taskkill /F /T /PID $procId 2>$null | Out-Null
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Step "호스트 API/Vite 종료 (8000, 5173)"
Stop-PortListeners @(8000, 5173)
# spawn worker 가 남는 경우
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
    Write-Step "docker compose stop (전체)"
    docker compose stop
}
else {
    Write-Step "docker compose stop db"
    docker compose stop db
}

Start-Sleep -Seconds 1
$left5173 = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
$left8000 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($left5173) { Write-Host "경고: 5173 아직 Listen" -ForegroundColor Yellow } else { Write-Host "5173 free" }
if ($left8000) { Write-Host "경고: 8000 아직 Listen" -ForegroundColor Yellow } else { Write-Host "8000 free" }

Write-Host ""
Write-Host "종료 완료" -ForegroundColor Green
