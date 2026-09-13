"""
제어 규칙·명령·이벤트 (2단계 Day 6).

테이블 역할
-----------
- ControlRule   : 자동 제어 조건 (히스테리시스 start/stop threshold)
- ControlCommand: 액추에이터에 대한 **목표** 명령 (idempotency_key)
- ControlEvent  : 명령의 **적용 결과** (append-only)

불변조건
--------
- Command 와 Event 를 한 테이블에 합치지 않는다.
- 규칙 변경은 version 을 증가시킨다.
- 동일 idempotency_key 로 중복 명령을 막는다.
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
from app.domain.enums import (
    ActuatorMode,
    ActuatorType,
    ControlCommandStatus,
    ControlEventType,
    RuleComparator,
    SensorType,
)

if TYPE_CHECKING:
    from app.db.models.equipment import Actuator
    from app.db.models.hierarchy import Farm, Room
    from app.db.models.simulation import SimulationRun


class ControlRule(TimestampMixin, Base):
    """
    재배실 자동 제어 규칙.

    start_threshold 로 명령을 내고 stop_threshold 로 정지한다 (히스테리시스).
    동일 (room_id, name, version) 조합은 유일하다 — 변경 시 version++ 로 새 행 또는 갱신.
    """

    __tablename__ = "control_rules"
    __table_args__ = (
        UniqueConstraint(
            "room_id",
            "name",
            "version",
            name="uq_control_rules_room_name_version",
        ),
        CheckConstraint("version >= 1", name="ck_control_rules_version_positive"),
        CheckConstraint("priority >= 0", name="ck_control_rules_priority_nonneg"),
        CheckConstraint(
            "cooldown_seconds >= 0",
            name="ck_control_rules_cooldown_nonneg",
        ),
        CheckConstraint(
            "min_on_seconds >= 0",
            name="ck_control_rules_min_on_nonneg",
        ),
        CheckConstraint(
            "target_output_ratio >= 0 AND target_output_ratio <= 1",
            name="ck_control_rules_output_ratio",
        ),
        Index("ix_control_rules_room_enabled_priority", "room_id", "enabled", "priority"),
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
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    metric: Mapped[SensorType] = mapped_column(str_enum(SensorType), nullable=False)
    comparator: Mapped[RuleComparator] = mapped_column(
        str_enum(RuleComparator, length=8),
        nullable=False,
        default=RuleComparator.GT,
    )
    start_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    stop_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    target_actuator_type: Mapped[ActuatorType] = mapped_column(
        str_enum(ActuatorType),
        nullable=False,
    )
    target_mode: Mapped[ActuatorMode] = mapped_column(
        str_enum(ActuatorMode, length=16),
        nullable=False,
        default=ActuatorMode.ON,
    )
    target_output_ratio: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )
    cooldown_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    min_on_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    description: Mapped[str | None] = mapped_column(Text)

    farm: Mapped[Farm] = relationship()
    room: Mapped[Room] = relationship()
    commands: Mapped[list[ControlCommand]] = relationship(back_populates="rule")


class ControlCommand(Base):
    """
    액추에이터에 대한 목표 명령.

    적용 성공/실패는 ControlEvent 로만 기록한다.
    """

    __tablename__ = "control_commands"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_control_commands_idempotency_key",
        ),
        CheckConstraint(
            "desired_output_ratio >= 0 AND desired_output_ratio <= 1",
            name="ck_control_commands_output_ratio",
        ),
        Index(
            "ix_control_commands_run_simulation_time",
            "simulation_run_id",
            "simulation_time",
        ),
        Index("ix_control_commands_actuator_id_issued_at", "actuator_id", "issued_at"),
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
    actuator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("actuators.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("control_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[ControlCommandStatus] = mapped_column(
        str_enum(ControlCommandStatus, length=16),
        nullable=False,
        default=ControlCommandStatus.PENDING,
        index=True,
    )
    desired_mode: Mapped[ActuatorMode] = mapped_column(
        str_enum(ActuatorMode, length=16),
        nullable=False,
    )
    desired_output_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    simulation_time: Mapped[float] = mapped_column(Float, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)

    simulation_run: Mapped[SimulationRun] = relationship()
    actuator: Mapped[Actuator] = relationship()
    rule: Mapped[ControlRule | None] = relationship(back_populates="commands")
    events: Mapped[list[ControlEvent]] = relationship(back_populates="command")


class ControlEvent(Base):
    """명령 적용·정지·실패 결과. command 행을 덮어쓰지 않고 append 한다."""

    __tablename__ = "control_events"
    __table_args__ = (
        Index(
            "ix_control_events_command_id_simulation_time",
            "command_id",
            "simulation_time",
        ),
        Index(
            "ix_control_events_run_simulation_time",
            "simulation_run_id",
            "simulation_time",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    command_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("control_commands.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    simulation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[ControlEventType] = mapped_column(
        str_enum(ControlEventType, length=16),
        nullable=False,
        index=True,
    )
    actual_output_ratio: Mapped[float | None] = mapped_column(Float)
    message: Mapped[str | None] = mapped_column(Text)
    simulation_time: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    command: Mapped[ControlCommand] = relationship(back_populates="events")
    simulation_run: Mapped[SimulationRun] = relationship()
