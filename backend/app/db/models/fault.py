"""
센서 고장 주입 정의·이력 (2단계 Day 6).

원시 sensor_readings 는 덮어쓰지 않는다.
주입은 측정 생성 경로에서 적용되고, 이 테이블은 시작·해제 이력을 남긴다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin
from app.db.models.types import str_enum
from app.domain.enums import FaultType

if TYPE_CHECKING:
    from app.db.models.equipment import Sensor
    from app.db.models.simulation import SimulationRun


class FaultInjection(TimestampMixin, Base):
    """
    고장 주입 하나.

    - active=True 이고 end_simulation_time 이 null 이면 진행 중
    - 해제 시 end_simulation_time / cleared_at 을 채우고 active=False
    """

    __tablename__ = "fault_injections"
    __table_args__ = (
        CheckConstraint(
            "end_simulation_time IS NULL OR end_simulation_time >= start_simulation_time",
            name="ck_fault_injections_time_order",
        ),
        Index(
            "ix_fault_injections_run_sensor_active",
            "simulation_run_id",
            "sensor_id",
            "active",
        ),
        Index(
            "ix_fault_injections_run_start_time",
            "simulation_run_id",
            "start_simulation_time",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    simulation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sensor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sensors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fault_type: Mapped[FaultType] = mapped_column(
        str_enum(FaultType, length=16),
        nullable=False,
        index=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # spike: 가산/배수, stuck: 고정값, dropout: 보통 null magnitude
    magnitude: Mapped[float | None] = mapped_column(Float)
    stuck_value: Mapped[float | None] = mapped_column(Float)
    start_simulation_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_simulation_time: Mapped[float | None] = mapped_column(Float)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    simulation_run: Mapped[SimulationRun] = relationship()
    sensor: Mapped[Sensor] = relationship()
