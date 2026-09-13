# backend

FarmTwin FastAPI API.

- Python **3.12** (`../.python-version`, `.python-version`)
- 패키지 관리: `uv`
- 테스트: `tests/`

```bash
cp .env.example .env   # 최초 1회
uv sync
uv run alembic upgrade head
uv run pytest
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- `GET /health` — 프로세스 생존
- `GET /health/ready` — DB 연결
- migration 되돌리기: `uv run alembic downgrade -1`
