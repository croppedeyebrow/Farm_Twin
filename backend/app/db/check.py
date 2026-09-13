"""
DB 연결 수동 점검 스크립트 (1단계 Day 2).

사용:
    cd backend
    uv run python -m app.db.check

Compose 없이도 API readiness 전에 DB만 빠르게 확인할 때 쓴다.
성공 시 `Database connection OK: 1` 을 출력한다.
"""

import asyncio

from sqlalchemy import text

from app.db.session import engine


async def check_database() -> None:
    """엔진으로 SELECT 1 을 실행하고 연결을 정리한다."""
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))
        print(f"Database connection OK: {result.scalar_one()}")

    # 스크립트 종료 전 풀을 닫아 경고/행잉을 막는다.
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_database())
