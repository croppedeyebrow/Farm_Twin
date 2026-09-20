<#
.SYNOPSIS
  FarmTwin 로컬 개발 스택 일괄 기동 (DB Docker + API + Vite).

.DESCRIPTION
  1) Docker Desktop 확인
  2) compose db 기동 + healthy 대기
  3) backend/.env 없으면 example 복사
  4) alembic migrate + seed
  5) uvicorn(8000), Vite(5173) 를 새 창에서 실행

  브라우저: http://127.0.0.1:5173
  (Compose 전체 스택은 -FullCompose → http://127.0.0.1:8080)

.PARAMETER SkipSeed
  seed 를 건너뛴다 (이미 데이터가 있을 때).

.PARAMETER FullCompose
  db/api/frontend/nginx 를 docker compose up --build 로만 기동한다.
  핫 리로드 없이 통합 진입점(8080)만 필요할 때 사용.
#>
param(
    [switch]$SkipSeed,
    [switch]$FullCompose
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-Docker {
    Write-Step "Docker Desktop 확인"
    try {
        docker info 1>$null 2>$null
        if ($LASTEXITCODE -ne 0) { throw "docker info failed" }
    }
    catch {
        throw "Docker Desktop가 꺼져 있거나 응답하지 않습니다. Docker를 켠 뒤 다시 실행하세요."
    }
}

function Ensure-EnvFiles {
    Write-Step ".env 준비"
    if (-not (Test-Path (Join-Path $Root ".env"))) {
        Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
        Write-Host "루트 .env 생성 (.env.example 복사)"
    }
    $backendEnv = Join-Path $Root "backend\.env"
    if (-not (Test-Path $backendEnv)) {
        Copy-Item (Join-Path $Root "backend\.env.example") $backendEnv
        Write-Host "backend/.env 생성 (.env.example 복사, host DB=15432)"
    }
}

function Wait-DbHealthy {
    Write-Step "DB healthy 대기"
    $deadline = (Get-Date).AddMinutes(2)
    do {
        $status = docker inspect --format="{{.State.Health.Status}}" farmtwin-db 2>$null
        if ($status -eq "healthy") {
            Write-Host "farmtwin-db healthy"
            return
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    throw "DB가 2분 안에 healthy 되지 않았습니다. docker compose logs db 를 확인하세요."
}

function Start-FullCompose {
    Write-Step "docker compose up --build -d (db+api+frontend+nginx)"
    Ensure-EnvFiles
    docker compose up --build -d
    if ($LASTEXITCODE -ne 0) { throw "docker compose up 실패" }

    Write-Step "seed (호스트 → DB 15432)"
    if (-not $SkipSeed) {
        Push-Location (Join-Path $Root "backend")
        try {
            uv run python -m app.db.seed
        }
        finally {
            Pop-Location
        }
    }

    Write-Host ""
    Write-Host "기동 완료" -ForegroundColor Green
    Write-Host "  UI : http://127.0.0.1:8080"
    Write-Host "  API: http://127.0.0.1:8080/api/health"
    Write-Host "종료: .\scripts\dev-down.ps1 -FullCompose"
}

function Start-LocalDev {
    Assert-Docker
    Ensure-EnvFiles

    Write-Step "DB 컨테이너 기동 (docker compose up -d db)"
    docker compose up -d db
    if ($LASTEXITCODE -ne 0) { throw "db 기동 실패" }
    Wait-DbHealthy

    Write-Step "backend migrate / seed"
    Push-Location (Join-Path $Root "backend")
    try {
        uv sync
        if ($LASTEXITCODE -ne 0) { throw "uv sync 실패" }
        uv run alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw "alembic 실패" }
        if (-not $SkipSeed) {
            uv run python -m app.db.seed
            if ($LASTEXITCODE -ne 0) { throw "seed 실패" }
        }
    }
    finally {
        Pop-Location
    }

    Write-Step "frontend 의존성"
    Push-Location (Join-Path $Root "frontend")
    try {
        if (-not (Test-Path "node_modules")) {
            npm install
            if ($LASTEXITCODE -ne 0) { throw "npm install 실패" }
        }
    }
    finally {
        Pop-Location
    }

    Write-Step "API / Vite 새 창 기동"
    $backendCmd = @"
Set-Location '$Root\backend'
Write-Host 'FarmTwin API  http://127.0.0.1:8000' -ForegroundColor Green
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"@
    $frontendCmd = @"
Set-Location '$Root\frontend'
Write-Host 'FarmTwin Vite  http://127.0.0.1:5173' -ForegroundColor Green
npm run dev -- --host 127.0.0.1 --port 5173
"@

    Start-Process powershell -WorkingDirectory (Join-Path $Root "backend") -ArgumentList @(
        "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $backendCmd
    )
    Start-Process powershell -WorkingDirectory (Join-Path $Root "frontend") -ArgumentList @(
        "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $frontendCmd
    )

    Write-Host ""
    Write-Host "기동 완료" -ForegroundColor Green
    Write-Host "  UI : http://127.0.0.1:5173"
    Write-Host "  API: http://127.0.0.1:8000/health"
    Write-Host "  DB : localhost:15432 (container farmtwin-db)"
    Write-Host "종료: .\scripts\dev-down.ps1"
}

Assert-Docker
if ($FullCompose) {
    Start-FullCompose
}
else {
    Start-LocalDev
}
