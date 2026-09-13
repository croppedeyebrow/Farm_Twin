"""
Alembic 환경 설정 (1단계 Day 2).

왜 async 인가
-------------
앱 런타임이 async SQLAlchemy + asyncpg 이므로 migration 도 같은 드라이버를 쓴다.
Alembic 자체는 sync API 이므로 `connection.run_sync(do_run_migrations)` 로 연결한다.

URL 출처
--------
alembic.ini 의 sqlalchemy.url 대신 `Settings.database_url` 을 강제한다.
로컬/Compose/CI 환경변수를 한곳에서 관리하기 위함이다.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.db.base import Base

config = context.config
# ini 파일 값보다 앱 설정을 우선한다.
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 2단계 이후 모델이 Base 에 등록되면 autogenerate 가 이 메타데이터를 비교한다.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """DB 연결 없이 SQL 스크립트만 생성할 때 (offline mode)."""
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """동기 컨텍스트에서 revision 을 실제로 적용한다."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    async 엔진을 만들고 sync migration 콜백을 실행한다.

    NullPool: migration 은 단발성이라 커넥션 풀링이 필요 없다.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"ssl": False},
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """온라인 모드 진입점. `alembic upgrade/downgrade` 가 여기를 탄다."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
