"""
공통 컬럼 mixin (2단계 Day 4).

생성/수정 시각을 메타데이터 테이블에 동일하게 둔다.

주의
----
시계열의 sampled_at / ingested_at / simulation_time 과는 의미가 다르다.
(time_semantics.py / 시간_컬럼_의미.md 참고)
TimestampMixin 은 Site/Farm/Sensor 같은 **카탈로그** 행에만 쓴다.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """
    created_at / updated_at 표준 컬럼.

    - server_default=now(): INSERT 시 DB 시각
    - onupdate=now(): ORM UPDATE 시 갱신 (raw SQL UPDATE 는 별도)
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
