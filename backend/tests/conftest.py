"""
pytest 공통 fixture.

Day 7+ 통합 테스트는 PostGIS 가 필요하다.
CI 는 workflow services 로 DB 를 띄우고, 로컬은 `docker compose up -d db` 후
`alembic upgrade head` 한 뒤 돌리면 된다.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.session import engine


@pytest.fixture
async def require_postgres() -> None:
    """DB 연결 불가 시 해당 테스트 스킵 (로컬에 PostGIS 없을 때)."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — 연결 실패면 통합 테스트 스킵
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable: {exc}")
