<#
.SYNOPSIS
  FarmTwin local stack: Docker DB + API + Vite.

.DESCRIPTION
  1) Check Docker Desktop
  2) Start compose db and wait healthy
  3) Copy .env from example if missing
  4) alembic migrate + seed
  5) Start uvicorn(8000) and Vite(5173) in new windows

  Browser: http://127.0.0.1:5173
  Full compose stack: -FullCompose -> http://127.0.0.1:8080

.PARAMETER SkipSeed
  Skip seed when data already exists.

.PARAMETER FullCompose
  Run db/api/frontend/nginx via docker compose up --build only.
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
    Write-Step "Checking Docker Desktop"
    # PowerShell treats docker stderr WARNINGs as errors when ErrorActionPreference=Stop.
    # Check exit code only; ignore warning text on stderr.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    docker info 1>$null 2>$null
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($code -ne 0) {
        throw "Docker Desktop is not running (docker info exit $code). Start Docker and retry."
    }
    Write-Host "Docker engine OK"
}

function Ensure-EnvFiles {
    Write-Step "Preparing .env files"
    if (-not (Test-Path (Join-Path $Root ".env"))) {
        Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
        Write-Host "Created root .env from .env.example"
    }
    $backendEnv = Join-Path $Root "backend\.env"
    if (-not (Test-Path $backendEnv)) {
        Copy-Item (Join-Path $Root "backend\.env.example") $backendEnv
        Write-Host "Created backend/.env from .env.example (host DB port 15432)"
    }
}

function Wait-DbHealthy {
    Write-Step "Waiting for DB healthy"
    $deadline = (Get-Date).AddMinutes(2)
    do {
        $status = docker inspect --format="{{.State.Health.Status}}" farmtwin-db 2>$null
        if ($status -eq "healthy") {
            Write-Host "farmtwin-db healthy"
            return
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    throw "DB did not become healthy within 2 minutes. Check: docker compose logs db"
}

function Start-FullCompose {
    Write-Step "docker compose up --build -d (db+api+frontend+nginx)"
    Ensure-EnvFiles
    docker compose up --build -d
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }

    Write-Step "seed (host -> DB 15432)"
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
    Write-Host "Started" -ForegroundColor Green
    Write-Host "  UI : http://127.0.0.1:8080"
    Write-Host "  API: http://127.0.0.1:8080/api/health"
    Write-Host "Stop: .\scripts\dev-down.ps1 -FullCompose"
}

function Start-LocalDev {
    Assert-Docker
    Ensure-EnvFiles

    Write-Step "Starting DB (docker compose up -d db)"
    docker compose up -d db
    if ($LASTEXITCODE -ne 0) { throw "db start failed" }
    Wait-DbHealthy

    Write-Step "backend migrate / seed"
    Push-Location (Join-Path $Root "backend")
    try {
        uv sync
        if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }
        uv run alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw "alembic failed" }
        if (-not $SkipSeed) {
            uv run python -m app.db.seed
            if ($LASTEXITCODE -ne 0) { throw "seed failed" }
        }
    }
    finally {
        Pop-Location
    }

    Write-Step "frontend dependencies"
    Push-Location (Join-Path $Root "frontend")
    try {
        if (-not (Test-Path "node_modules")) {
            npm install
            if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
        }
    }
    finally {
        Pop-Location
    }

    Write-Step "Starting API / Vite in new windows"
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
    Write-Host "Started" -ForegroundColor Green
    Write-Host "  UI : http://127.0.0.1:5173"
    Write-Host "  API: http://127.0.0.1:8000/health"
    Write-Host "  DB : localhost:15432 (container farmtwin-db)"
    Write-Host "Stop: .\scripts\dev-down.ps1"
}

Assert-Docker
if ($FullCompose) {
    Start-FullCompose
}
else {
    Start-LocalDev
}