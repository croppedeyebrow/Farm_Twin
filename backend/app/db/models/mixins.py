"""
공통 컬럼 mixin (2단계 Day 4).

생성/수정 시각을 모든 메타데이터 테이블에 동일하게 둔다.
시계열의 sampled_at / simulation_time 과는 의미가 다르다.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """created_at / updated_at 표준 컬럼."""

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
