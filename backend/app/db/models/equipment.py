"""
센서·액추에이터 메타데이터 모델 (2단계 Day 4).

역할
----
"무엇이 어디에 설치되었는지" 만 정의한다.
시계열(readings)·명령/이벤트는 Day 5~6 테이블이 담당한다.

Sensor
------
- room_id 필수, rack_id 선택 (룸 공용 vs 랙 부착)
- unit 은 seed 시 `default_unit_for(sensor_type)` 로 맞춘다
- model_version: 가상 센서 모델 lineage (재현성)

Actuator
--------
- mode / output_ratio: **현재 운전 상태 캐시**
- 이력은 control_commands / control_events 에 append
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin
from app.db.models.types import str_enum
from app.domain.enums import ActuatorMode, ActuatorType, SensorType, Unit

if TYPE_CHECKING:
    from app.db.models.hierarchy import Rack, Room


class Sensor(TimestampMixin, Base):
    """센서 메타데이터. readings 는 sensor_readings 테이블."""

    __tablename__ = "sensors"
    __table_args__ = (
        UniqueConstraint("room_id", "code", name="uq_sensors_room_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 랙 부착이면 설정, 룸 공용이면 null (예: 배지수분만 랙)
    rack_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("racks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sensor_type: Mapped[SensorType] = mapped_column(
        str_enum(SensorType),
        nullable=False,
        index=True,
    )
    unit: Mapped[Unit] = mapped_column(str_enum(Unit), nullable=False)
    # 가상 센서 모델 버전 — 재현성/lineage 용
    model_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="v1",
        server_default="v1",
    )

    room: Mapped[Room] = relationship(back_populates="sensors")
    rack: Mapped[Rack | None] = relationship(back_populates="sensors")


class Actuator(TimestampMixin, Base):
    """액추에이터 메타데이터 + 현재 운전 캐시."""

    __tablename__ = "actuators"
    __table_args__ = (
        UniqueConstraint("room_id", "code", name="uq_actuators_room_code"),
        CheckConstraint(
            "output_ratio >= 0 AND output_ratio <= 1",
            name="ck_actuators_output_ratio",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    actuator_type: Mapped[ActuatorType] = mapped_column(
        str_enum(ActuatorType),
        nullable=False,
        index=True,
    )
    mode: Mapped[ActuatorMode] = mapped_column(
        str_enum(ActuatorMode, length=16),
        nullable=False,
        default=ActuatorMode.OFF,
        server_default=ActuatorMode.OFF.value,
    )
    # 0.0~1.0 출력 비율. OFF 이면 보통 0.
    output_ratio: Mapped[float] = mapped_column(
        nullable=False,
        default=0.0,
        server_default="0",
    )

    room: Mapped[Room] = relationship(back_populates="actuators")
