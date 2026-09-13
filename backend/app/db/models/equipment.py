"""
센서·액추에이터 메타데이터 모델 (2단계 Day 4).

시계열(readings)과 명령/이벤트는 Day 5~6 테이블이 담당한다.
여기 테이블은 "무엇이 어디에 설치되었는지" 만 정의한다.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin
from app.db.models.types import str_enum
from app.domain.enums import ActuatorMode, ActuatorType, SensorType, Unit

if TYPE_CHECKING:
    from app.db.models.hierarchy import Rack, Room


class Sensor(TimestampMixin, Base):
    """
    센서 메타데이터.

    - room_id: 소속 재배실 (필수)
    - rack_id: 랙 부착 센서면 설정, 룸 공용이면 null
    - unit: 정규화 저장 단위 (SensorType 기본값과 일치시키는 것을 권장)
    """

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
    """
    액추에이터 메타데이터.

    현재 운전 상태는 여기의 mode/output_ratio 로 캐시하고,
    이력은 control_commands / control_events (Day 6) 에 남긴다.
    """

    __tablename__ = "actuators"
    __table_args__ = (
        UniqueConstraint("room_id", "code", name="uq_actuators_room_code"),
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
