"""
환경 참값·센서 측정값 (2단계 Day 5).

구분 (절대 혼동 금지)
--------------------
- FarmState     : 시뮬레이터가 계산한 환경 **참값**
                  room 당 최신 1행 + version 단조 증가. 센서 noise 없음.
- SensorReading : 가상 센서가 관측한 **측정값**
                  오차·고장·품질 포함, append-only (원본 수정 금지).

명령/적용 결과는 Day 6 Control* 테이블이 담당한다.
센서 noise 는 FarmState 를 바꾸지 않는다 (3단계 완료 기준).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin
from app.db.models.types import str_enum
from app.domain.enums import ReadingQuality, ReadingSource, Unit

if TYPE_CHECKING:
    from app.db.models.equipment import Sensor
    from app.db.models.hierarchy import Farm, Room
    from app.db.models.simulation import SimulationRun


class FarmState(TimestampMixin, Base):
    """
    재배실 환경 참값의 현재 스냅샷.

    보존정책: 최신 1행/room. version 은 갱신마다 단조 증가한다.
    이력 재생이 필요하면 simulation_run_id + simulation_time 으로 추적한다.
    """

    __tablename__ = "farm_states"
    __table_args__ = (
        UniqueConstraint("room_id", name="uq_farm_states_room"),
        CheckConstraint("version >= 1", name="ck_farm_states_version_positive"),
    )

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
    simulation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulation_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # 참값 (센서 노이즈 없음)
    temperature_c: Mapped[float] = mapped_column(Float, nullable=False)
    humidity_pct: Mapped[float] = mapped_column(Float, nullable=False)
    co2_ppm: Mapped[float] = mapped_column(Float, nullable=False)
    substrate_moisture_pct: Mapped[float] = mapped_column(Float, nullable=False)
    ppfd_umol: Mapped[float] = mapped_column(Float, nullable=False)
    simulation_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    farm: Mapped[Farm] = relationship()
    room: Mapped[Room] = relationship()
    simulation_run: Mapped[SimulationRun | None] = relationship(
        back_populates="farm_states",
    )


class SensorReading(Base):
    """
    가상 센서 시계열 (append-only, 원본 수정 금지).

    인덱스(설계):
    - (sensor_id, simulation_time DESC)
    - (simulation_run_id, sequence) UNIQUE
    """

    __tablename__ = "sensor_readings"
    __table_args__ = (
        UniqueConstraint(
            "simulation_run_id",
            "sequence",
            name="uq_sensor_readings_run_sequence",
        ),
        CheckConstraint("sequence >= 0", name="ck_sensor_readings_sequence_nonneg"),
        # 센서별 최신 이력 조회용 (정렬은 쿼리에서 DESC)
        Index(
            "ix_sensor_readings_sensor_id_simulation_time",
            "sensor_id",
            "simulation_time",
        ),
        Index(
            "ix_sensor_readings_farm_id_simulation_time",
            "farm_id",
            "simulation_time",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    sensor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sensors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 조회 편의용 비정규화 (farm 단위 시계열 인덱스 후보)
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
    simulation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[Unit] = mapped_column(str_enum(Unit), nullable=False)
    quality: Mapped[ReadingQuality] = mapped_column(
        str_enum(ReadingQuality, length=16),
        nullable=False,
        default=ReadingQuality.GOOD,
        index=True,
    )
    source: Mapped[ReadingSource] = mapped_column(
        str_enum(ReadingSource, length=32),
        nullable=False,
        default=ReadingSource.SIMULATED,
    )
    sensor_model_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="v1",
    )
    simulation_time: Mapped[float] = mapped_column(Float, nullable=False)
    sampled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    sensor: Mapped[Sensor] = relationship()
    simulation_run: Mapped[SimulationRun] = relationship(
        back_populates="sensor_readings",
    )
