"""
비동기 DB 엔진·세션 (1단계 Day 2 / 2단계 Day 7).

FastAPI Depends(get_db) 로 요청 단위 세션을 제공한다.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    connect_args={"ssl": False},
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """요청 스코프 DB 세션. 커밋은 서비스/라우터에서 명시한다."""
    async with SessionLocal() as session:
        yield session
