#!/usr/bin/env bash
# FarmTwin 로컬 개발 스택 일괄 기동 (Linux/macOS/Git Bash).
# Windows 는 scripts/dev-up.ps1 을 사용한다.
#
# 사용:
#   ./scripts/dev-up.sh
#   ./scripts/dev-up.sh --skip-seed
#   ./scripts/dev-up.sh --full-compose
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SKIP_SEED=0
FULL_COMPOSE=0
for arg in "$@"; do
  case "$arg" in
    --skip-seed) SKIP_SEED=1 ;;
    --full-compose) FULL_COMPOSE=1 ;;
    *) echo "unknown arg: $arg" >&2; exit 1 ;;
  esac
done

step() { printf '\n==> %s\n' "$1"; }

assert_docker() {
  step "Docker 확인"
  if ! docker info >/dev/null 2>&1; then
    echo "Docker가 꺼져 있습니다. Docker를 켠 뒤 다시 실행하세요." >&2
    exit 1
  fi
}

ensure_env() {
  step ".env 준비"
  [[ -f .env ]] || cp .env.example .env
  [[ -f backend/.env ]] || cp backend/.env.example backend/.env
}

wait_db() {
  step "DB healthy 대기"
  for _ in $(seq 1 60); do
    status="$(docker inspect --format='{{.State.Health.Status}}' farmtwin-db 2>/dev/null || true)"
    if [[ "$status" == "healthy" ]]; then
      echo "farmtwin-db healthy"
      return 0
    fi
    sleep 2
  done
  echo "DB healthy 대기 시간 초과" >&2
  exit 1
}

assert_docker
ensure_env

if [[ "$FULL_COMPOSE" -eq 1 ]]; then
  step "docker compose up --build -d"
  docker compose up --build -d
  if [[ "$SKIP_SEED" -eq 0 ]]; then
    step "seed"
    (cd backend && uv run python -m app.db.seed)
  fi
  echo
  echo "기동 완료"
  echo "  UI : http://127.0.0.1:8080"
  echo "종료: ./scripts/dev-down.sh --full-compose"
  exit 0
fi

step "DB 기동"
docker compose up -d db
wait_db

step "backend migrate / seed"
(
  cd backend
  uv sync
  uv run alembic upgrade head
  if [[ "$SKIP_SEED" -eq 0 ]]; then
    uv run python -m app.db.seed
  fi
)

step "frontend deps"
(
  cd frontend
  [[ -d node_modules ]] || npm install
)

step "API + Vite (백그라운드)"
mkdir -p .run
(
  cd backend
  nohup uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 \
    >"$ROOT/.run/api.log" 2>&1 &
  echo $! >"$ROOT/.run/api.pid"
)
(
  cd frontend
  nohup npm run dev -- --host 127.0.0.1 --port 5173 \
    >"$ROOT/.run/vite.log" 2>&1 &
  echo $! >"$ROOT/.run/vite.pid"
)

echo
echo "기동 완료"
echo "  UI : http://127.0.0.1:5173"
echo "  API: http://127.0.0.1:8000/health"
echo "  로그: .run/api.log , .run/vite.log"
echo "종료: ./scripts/dev-down.sh"
