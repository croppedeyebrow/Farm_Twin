"""2단계 Day 6 — 제어·고장주입 모델 및 제약 테스트."""

from app.db.base import Base
from app.db.models import (
    Actuator,
    ControlCommand,
    ControlEvent,
    ControlRule,
    FaultInjection,
)
from app.domain.enums import ControlCommandStatus, ControlEventType, FaultType


def test_day6_tables_registered() -> None:
    names = set(Base.metadata.tables)
    assert {
        "control_rules",
        "control_commands",
        "control_events",
        "fault_injections",
    } <= names


def test_command_and_event_are_separate_tables() -> None:
    assert ControlCommand.__tablename__ != ControlEvent.__tablename__
    assert "command_id" in ControlEvent.__table__.c
    assert "idempotency_key" in ControlCommand.__table__.c


def test_control_command_idempotency_unique() -> None:
    names = {c.name for c in ControlCommand.__table__.constraints if c.name}
    assert "uq_control_commands_idempotency_key" in names


def test_control_rule_version_unique() -> None:
    names = {c.name for c in ControlRule.__table__.constraints if c.name}
    assert "uq_control_rules_room_name_version" in names
    assert "ck_control_rules_version_positive" in names


def test_fault_injection_time_order_check() -> None:
    names = {c.name for c in FaultInjection.__table__.constraints if c.name}
    assert "ck_fault_injections_time_order" in names


def test_actuator_output_ratio_check() -> None:
    names = {c.name for c in Actuator.__table__.constraints if c.name}
    assert "ck_actuators_output_ratio" in names


def test_control_foreign_keys() -> None:
    assert ControlRule.__table__.c.room_id.foreign_keys
    assert ControlCommand.__table__.c.actuator_id.foreign_keys
    assert ControlCommand.__table__.c.simulation_run_id.foreign_keys
    assert ControlEvent.__table__.c.command_id.foreign_keys
    assert FaultInjection.__table__.c.sensor_id.foreign_keys


def test_control_query_indexes() -> None:
    command_indexes = {idx.name for idx in ControlCommand.__table__.indexes}
    event_indexes = {idx.name for idx in ControlEvent.__table__.indexes}
    fault_indexes = {idx.name for idx in FaultInjection.__table__.indexes}
    assert "ix_control_commands_run_simulation_time" in command_indexes
    assert "ix_control_events_command_id_simulation_time" in event_indexes
    assert "ix_fault_injections_run_sensor_active" in fault_indexes


def test_day6_enums() -> None:
    assert set(FaultType) == {FaultType.SPIKE, FaultType.STUCK, FaultType.DROPOUT}
    assert ControlCommandStatus.PENDING.value == "pending"
    assert ControlEventType.APPLIED.value == "applied"
