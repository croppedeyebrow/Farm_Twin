#!/usr/bin/env bash
# FarmTwin 로컬 개발 스택 종료 (Linux/macOS/Git Bash).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FULL_COMPOSE=0
for arg in "$@"; do
  case "$arg" in
    --full-compose) FULL_COMPOSE=1 ;;
    *) echo "unknown arg: $arg" >&2; exit 1 ;;
  esac
done

step() { printf '\n==> %s\n' "$1"; }

stop_pidfile() {
  local file="$1"
  if [[ -f "$file" ]]; then
    local pid
    pid="$(cat "$file")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "stop PID $pid ($file)"
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$file"
  fi
}

step "호스트 API/Vite 종료"
stop_pidfile "$ROOT/.run/api.pid"
stop_pidfile "$ROOT/.run/vite.pid"
# 포트 기반 보조 정리
if command -v lsof >/dev/null 2>&1; then
  for port in 8000 5173; do
    pids="$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "$pids" ]]; then
      echo "kill port $port: $pids"
      # shellcheck disable=SC2086
      kill $pids 2>/dev/null || true
    fi
  done
fi

if [[ "$FULL_COMPOSE" -eq 1 ]]; then
  step "docker compose stop (전체)"
  docker compose stop
else
  step "docker compose stop db"
  docker compose stop db
fi

echo
echo "종료 완료"
