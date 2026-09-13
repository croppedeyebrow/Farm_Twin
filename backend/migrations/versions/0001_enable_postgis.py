"""
초기 revision: PostGIS 확장 활성화 (1단계 Day 2).

Revision ID: 0001_enable_postgis
Revises:
Create Date: 2026-09-13

배경
----
DB 설계상 PostGIS 는 농장 좌표·기상 기준점의 공간관계에 사용한다.
도메인 테이블(2단계)에 앞서 확장을 먼저 올려 up/down 경로를 확보한다.

검증
----
    uv run alembic upgrade head
    uv run alembic downgrade -1
    uv run alembic upgrade head
"""

from collections.abc import Sequence

from alembic import op

# Alembic 이 revision 그래프를 구성할 때 읽는 식별자.
revision: str = "0001_enable_postgis"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """PostGIS 확장을 켠다. 이미 있으면 무시."""
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def downgrade() -> None:
    """확장을 제거한다. 이후 공간 컬럼이 생기면 먼저 그 컬럼을 지운 뒤 호출해야 한다."""
    op.execute("DROP EXTENSION IF EXISTS postgis")
