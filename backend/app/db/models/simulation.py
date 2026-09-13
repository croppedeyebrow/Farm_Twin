"""
시뮬레이션 실행·외기 스냅샷 (2단계 Day 5).

SimulationRun 은 한 번의 실험/데모 세션이다.
WeatherSnapshot 은 그 세션에 투입된 외기 입력 이력이다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin
from app.db.models.types import str_enum
from app.domain.enums import SimulationStatus, WeatherMode

if TYPE_CHECKING:
    from app.db.models.hierarchy import Farm, Room
    from app.db.models.telemetry import FarmState, SensorReading


class SimulationRun(TimestampMixin, Base):
    """
    시뮬레이션 실행 단위.

    불변조건(설계): 한 run 에는 active worker 하나만 허용한다.
    worker lease 컬럼은 4단계 제어 루프에서 본격 사용한다.
    """

    __tablename__ = "simulation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[SimulationStatus] = mapped_column(
        str_enum(SimulationStatus, length=16),
        nullable=False,
        default=SimulationStatus.CREATED,
        server_default=SimulationStatus.CREATED.value,
        index=True,
    )
    # 재현성
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    weather_mode: Mapped[WeatherMode] = mapped_column(
        str_enum(WeatherMode, length=16),
        nullable=False,
        default=WeatherMode.SYNTHETIC,
        server_default=WeatherMode.SYNTHETIC.value,
    )
    environment_model_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="v1",
        server_default="v1",
    )
    # 가상 시계(초). 시뮬레이터가 단조 증가시킨다.
    simulation_time_seconds: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )
    time_scale: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        server_default="1",
    )
    # wall-clock 구간 (운영 관측용). 가상 시계와 별개.
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # active worker 방어용 (4단계에서 lease 갱신)
    worker_id: Mapped[str | None] = mapped_column(String(128))
    worker_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    notes: Mapped[str | None] = mapped_column(Text)

    farm: Mapped[Farm] = relationship()
    room: Mapped[Room] = relationship()
    weather_snapshots: Mapped[list[WeatherSnapshot]] = relationship(
        back_populates="simulation_run",
    )
    farm_states: Mapped[list[FarmState]] = relationship(
        back_populates="simulation_run",
    )
    sensor_readings: Mapped[list[SensorReading]] = relationship(
        back_populates="simulation_run",
    )


class WeatherSnapshot(Base):
    """
    외기 입력 한 시점의 스냅샷.

    created_at 대신 sampled_at / ingested_at / simulation_time 을 쓴다.
    (시간 컬럼 의미: docs/.../시간_컬럼_의미.md)
    """

    __tablename__ = "weather_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "simulation_run_id",
            "sequence",
            name="uq_weather_snapshots_run_sequence",
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
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[WeatherMode] = mapped_column(
        str_enum(WeatherMode, length=16),
        nullable=False,
    )
    outdoor_temperature_c: Mapped[float] = mapped_column(Float, nullable=False)
    outdoor_humidity_pct: Mapped[float] = mapped_column(Float, nullable=False)
    # 가상 시계 시각(초)
    simulation_time: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    # 소스에서 샘플이 발생한 시각 (API/REPLAY 원본 시각)
    sampled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    # 시스템에 적재된 시각
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    simulation_run: Mapped[SimulationRun] = relationship(
        back_populates="weather_snapshots",
    )
