"""
비동기 DB 엔진 (1단계 Day 2).

FastAPI 엔드포인트와 Alembic online migration 이 같은 DATABASE_URL 을 쓴다.
드라이버는 asyncpg (`postgresql+asyncpg://...`).
"""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import settings

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    # 로컬 PostGIS 컨테이너는 TLS 를 쓰지 않는다.
    connect_args={"ssl": False},
    # 끊긴 커넥션을 checkout 시점에 감지해 재연결한다.
    pool_pre_ping=True,
)
