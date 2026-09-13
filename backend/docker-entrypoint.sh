#!/bin/sh
# API 컨테이너 기동 스크립트 (1단계 Day 3).
#
# 순서:
#   1) alembic upgrade head  — 스키마를 최신으로 맞춤
#   2) uvicorn              — HTTP/WebSocket 서버 기동
#
# `.venv/bin/*` 를 직접 호출하는 이유:
#   `uv run` 은 의존성을 다시 해석할 수 있어 이미지에 심은 frozen venv 와 어긋날 수 있다.
# `exec` 로 uvicorn 를 PID 1 에 올려 시그널(SIGTERM)이 프로세스에 전달되게 한다.
set -eu
.venv/bin/alembic upgrade head
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
