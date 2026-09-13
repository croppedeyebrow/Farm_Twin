"""
비동기 DB 엔진·세션 (1단계 Day 2 / 2단계 Day 7).

- engine: 프로세스 전역 커넥션 풀 (asyncpg)
- SessionLocal: 세션 팩토리
- get_db: FastAPI Depends 용 제너레이터

커밋 정책: 서비스/시드가 명시적으로 `session.commit()` 한다.
읽기 전용 핸들러는 commit 없이 세션 종료로 충분하다.
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
    # 로컬 PostGIS 컨테이너는 TLS 미사용
    connect_args={"ssl": False},
    # 끊긴 커넥션을 checkout 시 감지
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    # commit 후에도 속성 접근 가능 (API 응답 직렬화에 편리)
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """요청 스코프 DB 세션."""
    async with SessionLocal() as session:
        yield session
