"""
룸 자동제어 — 측정값·품질 기반 규칙 평가 (6단계 Day 22).

=============================================================================
위치
-----------------------------------------------------------------------------
step_run 한 스텝:
  참값 전이 → 측정(고장 적용) → 품질 판정·적재 → **여기** → 다음 스텝 설비 입력

규칙은 참값이 아니라 방금 판정한 측정값과 품질로 평가한다.
그래야 고장 난 센서가 제어 사고로 이어지는지를 재현·검증할 수 있다.

=============================================================================
품질 정책 (domain.control.quality)
-----------------------------------------------------------------------------
  good              → 값으로 START/STOP 판정
  suspect           → HOLD  (설비 상태 유지, 같은 설비의 하위 규칙도 막음)
  bad/missing/stale → SKIP  (새 명령 없음)

품질 때문에 막힌 규칙은 "차단 구간"이 시작될 때 한 번만 Command(CANCELLED) +
Event(REJECTED) 로 남긴다. 매 스텝 남기면 타임라인이 차단 기록으로 덮인다.

MANUAL 설비는 운영자가 점유 중이라 규칙이 건드리지 않는다.

=============================================================================
DB 멱등 키
-----------------------------------------------------------------------------
도메인 키({run}:{rule}:v{n}:{intent}:{mode}:{ratio})에는 시각이 없다.
control_commands.idempotency_key 는 UNIQUE 라 두 번째 냉방 사이클이 막히므로
DB 에는 `@{simulation_time}` 을 붙여 저장한다. 같은 스텝 재시도만 충돌한다.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Actuator,
    ControlCommand,
    ControlEvent,
    ControlRule,
    SimulationRun,
)
from app.domain.control.actuators import ActuatorSnapshot
from app.domain.control.commands import execute_decision
from app.domain.control.evaluate import MetricReading, RuleIntent, evaluate_rule
from app.domain.control.gates import ControlRuntime
from app.domain.control.quality import (
    DEFAULT_QUALITY_POLICY,
    QualityAction,
    QualityPolicy,
)
from app.domain.control.schema import RuleDefinition, RuleSet
from app.domain.enums import (
    ActuatorMode,
    ActuatorType,
    ControlCommandStatus,
    ControlEventType,
    ReadingQuality,
    SensorType,
)

IDEMPOTENCY_KEY_MAX_LENGTH = 128

# (run_id, rule_name) → 차단 중인 품질. 차단 구간 시작만 기록하려는 프로세스 메모리.
# 재시작하면 진행 중 차단이 한 번 더 기록될 뿐 제어 동작에는 영향이 없다.
_BLOCKED: dict[tuple[uuid.UUID, str], ReadingQuality] = {}


def clear_blocked_cache(run_id: uuid.UUID | None = None) -> None:
    if run_id is None:
        _BLOCKED.clear()
        return
    for key in [key for key in _BLOCKED if key[0] == run_id]:
        del _BLOCKED[key]


def rule_from_orm(rule: ControlRule) -> RuleDefinition:
    return RuleDefinition(
        name=rule.name,
        version=rule.version,
        enabled=rule.enabled,
        priority=rule.priority,
        metric=rule.metric,
        comparator=rule.comparator,
        start_threshold=rule.start_threshold,
        stop_threshold=rule.stop_threshold,
        target_actuator_type=rule.target_actuator_type,
        target_mode=rule.target_mode,
        target_output_ratio=rule.target_output_ratio,
        cooldown_seconds=rule.cooldown_seconds,
        min_on_seconds=rule.min_on_seconds,
        description=rule.description,
    )


def missing_reading(sensor_type: SensorType, last_value: float | None) -> MetricReading:
    """이번 스텝에 샘플이 오지 않은 센서 (dropout)."""
    return MetricReading(
        sensor_type=sensor_type,
        value=last_value if last_value is not None else math.nan,
        quality=ReadingQuality.MISSING,
    )


def _is_active(actuator: Actuator) -> bool:
    return actuator.mode is not ActuatorMode.OFF and actuator.output_ratio > 0.0


def _db_key(key: str, simulation_time: float) -> str:
    return f"{key}@{simulation_time:.3f}"[:IDEMPOTENCY_KEY_MAX_LENGTH]


async def _restore_runtime(
    session: AsyncSession,
    run_id: uuid.UUID,
    seed_gates: Mapping[str, Any] | None = None,
) -> ControlRuntime:
    """
    min_on / cooldown 게이트용 설비별 마지막 규칙 START/STOP 시각.

    seed_gates: 재생 run 의 체크포인트 게이트. 이 run 의 명령 이력이 뒤에 덮어쓴다.
    """
    runtime = ControlRuntime()
    for actuator_type, (last_start, last_stop) in (seed_gates or {}).items():
        timing = runtime.timing_for(ActuatorType(actuator_type))
        timing.last_start_sim_time = last_start
        timing.last_stop_sim_time = last_stop
    rows = await session.execute(
        select(ControlCommand.desired_mode, ControlCommand.simulation_time, Actuator.actuator_type)
        .join(Actuator, ControlCommand.actuator_id == Actuator.id)
        .where(
            ControlCommand.simulation_run_id == run_id,
            ControlCommand.rule_id.is_not(None),
            ControlCommand.status == ControlCommandStatus.SUCCEEDED,
        )
        .order_by(ControlCommand.simulation_time)
    )
    for mode, simulation_time, actuator_type in rows.all():
        if mode is ActuatorMode.OFF:
            runtime.record_stop(actuator_type, simulation_time)
        else:
            runtime.record_start(actuator_type, simulation_time)
    return runtime


@dataclass
class RoomController:
    """한 step_run 호출 동안 유지하는 룸 규칙 실행기 (commit 은 호출자)."""

    session: AsyncSession
    run: SimulationRun
    rules: list[tuple[ControlRule, RuleDefinition]]
    actuators: list[Actuator]
    runtime: ControlRuntime
    rule_set_version: str
    quality_policy: QualityPolicy = DEFAULT_QUALITY_POLICY
    commands_issued: int = 0
    blocked_recorded: int = 0
    changed_actuator_ids: set[uuid.UUID] = field(default_factory=set)

    @property
    def actuators_by_type(self) -> dict[ActuatorType, Actuator]:
        by_type: dict[ActuatorType, Actuator] = {}
        for actuator in self.actuators:
            by_type.setdefault(actuator.actuator_type, actuator)
        return by_type

    def evaluate(
        self,
        readings: Mapping[SensorType, MetricReading],
        *,
        simulation_time: float,
        now: datetime,
        reading_ids: Mapping[SensorType, uuid.UUID] | None = None,
    ) -> bool:
        """
        규칙 한 틱. 설비 상태가 바뀌었으면 True.

        reading_ids: 이번 스텝에 적재한 측정 행 — 명령의 판정 근거로 남긴다.
        dropout 처럼 행이 없는 판정은 근거가 비어 있다.
        """
        changed = False
        reading_ids = reading_ids or {}
        by_type = self.actuators_by_type
        claimed: set[ActuatorType] = set()

        for orm_rule, rule in self.rules:
            target = rule.target_actuator_type
            actuator = by_type.get(target)
            if actuator is None or target in claimed:
                continue

            decision = evaluate_rule(
                rule,
                reading=readings.get(rule.metric),
                actuator_active=_is_active(actuator),
                quality_policy=self.quality_policy,
            )
            block_key = (self.run.id, rule.name)
            action = (
                self.quality_policy.action_for(decision.quality)
                if decision.quality is not None
                else QualityAction.USE
            )
            if action is not QualityAction.USE:
                if action is QualityAction.HOLD:
                    claimed.add(target)
                if _BLOCKED.get(block_key) is not decision.quality:
                    _BLOCKED[block_key] = decision.quality
                    self._record_blocked(
                        orm_rule,
                        rule,
                        actuator,
                        quality=decision.quality,
                        action=action,
                        metric_value=decision.metric_value,
                        simulation_time=simulation_time,
                        now=now,
                        trigger_reading_id=reading_ids.get(rule.metric),
                    )
                continue
            _BLOCKED.pop(block_key, None)

            if decision.intent is RuleIntent.SKIP:
                continue
            claimed.add(target)
            if actuator.mode is ActuatorMode.MANUAL:
                continue

            application = execute_decision(
                decision,
                ActuatorSnapshot(
                    actuator_type=actuator.actuator_type,
                    mode=actuator.mode,
                    output_ratio=actuator.output_ratio,
                    code=actuator.code,
                ),
                simulation_time=simulation_time,
                run_key=str(self.run.id),
                rule=rule,
                runtime=self.runtime,
            )
            if application is None:
                continue

            command = ControlCommand(
                id=uuid.uuid4(),
                simulation_run_id=self.run.id,
                actuator_id=actuator.id,
                rule_id=orm_rule.id,
                idempotency_key=_db_key(application.command.idempotency_key, simulation_time),
                status=application.command.status,
                desired_mode=application.command.desired_mode,
                desired_output_ratio=application.command.desired_output_ratio,
                simulation_time=simulation_time,
                issued_at=now,
                reason=application.command.reason,
                rule_version=rule.version,
                trigger_reading_id=reading_ids.get(rule.metric),
            )
            self.session.add(command)
            self.session.add(
                ControlEvent(
                    command_id=command.id,
                    simulation_run_id=self.run.id,
                    event_type=application.event.event_type,
                    actual_output_ratio=application.event.actual_output_ratio,
                    message=application.event.message,
                    simulation_time=simulation_time,
                    recorded_at=now,
                )
            )
            self.commands_issued += 1
            after = application.actuator_after
            if (after.mode, after.output_ratio) != (actuator.mode, actuator.output_ratio):
                actuator.mode = after.mode
                actuator.output_ratio = after.output_ratio
                self.changed_actuator_ids.add(actuator.id)
                changed = True
        return changed

    def _record_blocked(
        self,
        orm_rule: ControlRule,
        rule: RuleDefinition,
        actuator: Actuator,
        *,
        quality: ReadingQuality | None,
        action: QualityAction,
        metric_value: float | None,
        simulation_time: float,
        now: datetime,
        trigger_reading_id: uuid.UUID | None,
    ) -> None:
        """품질 차단 구간 시작 — 설비는 그대로 두고 감사 기록만 남긴다."""
        quality_text = quality.value if quality is not None else "unknown"
        verb = "보류" if action is QualityAction.HOLD else "차단"
        shown = (
            f"{metric_value:.2f}"
            if metric_value is not None and math.isfinite(metric_value)
            else "없음"
        )
        message = (
            f"{rule.metric.value} 측정 품질 {quality_text}(값 {shown}) → "
            f"{rule.name} 자동제어 {verb}, 설비 상태 유지"
        )
        command = ControlCommand(
            id=uuid.uuid4(),
            simulation_run_id=self.run.id,
            actuator_id=actuator.id,
            rule_id=orm_rule.id,
            idempotency_key=_db_key(
                f"{self.run.id}:{rule.name}:v{rule.version}:blocked:{quality_text}",
                simulation_time,
            ),
            status=ControlCommandStatus.CANCELLED,
            desired_mode=actuator.mode,
            desired_output_ratio=actuator.output_ratio,
            simulation_time=simulation_time,
            issued_at=now,
            reason=f"quality {action.value}: {quality_text}",
            rule_version=rule.version,
            trigger_reading_id=trigger_reading_id,
        )
        self.session.add(command)
        self.session.add(
            ControlEvent(
                command_id=command.id,
                simulation_run_id=self.run.id,
                event_type=ControlEventType.REJECTED,
                actual_output_ratio=actuator.output_ratio,
                message=message,
                simulation_time=simulation_time,
                recorded_at=now,
            )
        )
        self.blocked_recorded += 1


async def control_checkpoint(session: AsyncSession, run_id: uuid.UUID) -> dict[str, Any]:
    """
    체크포인트용 제어 런타임 — 게이트 시각과 진행 중 품질 차단.

    재생 run 이 원본의 중간 시각에서 출발해도 min_on/cooldown 과
    "차단 구간 시작만 기록" 이 원본과 같게 동작하도록 함께 저장한다.
    """
    runtime = await _restore_runtime(session, run_id)
    return {
        "gates": {
            actuator_type.value: [timing.last_start_sim_time, timing.last_stop_sim_time]
            for actuator_type, timing in runtime.timing.items()
        },
        "blocked": {
            rule_name: quality.value
            for (blocked_run, rule_name), quality in _BLOCKED.items()
            if blocked_run == run_id and quality is not None
        },
    }


def seed_blocked(run_id: uuid.UUID, blocked: Mapping[str, str]) -> None:
    """재생 run 첫 스텝 — 원본 체크포인트 시점에 진행 중이던 품질 차단."""
    for rule_name, quality in blocked.items():
        _BLOCKED[(run_id, rule_name)] = ReadingQuality(quality)


async def open_room_controller(
    session: AsyncSession,
    run: SimulationRun,
    actuators: Iterable[Actuator],
    *,
    seed_gates: Mapping[str, Any] | None = None,
) -> RoomController:
    orm_rules = (
        await session.scalars(
            select(ControlRule).where(
                ControlRule.room_id == run.room_id,
                ControlRule.enabled.is_(True),
            )
        )
    ).all()
    definitions = {rule.id: rule_from_orm(rule) for rule in orm_rules}
    rule_set = RuleSet(rules=tuple(definitions.values()))
    ordered = rule_set.enabled_by_priority()
    by_name = {definitions[rule.id].name: rule for rule in orm_rules}
    return RoomController(
        session=session,
        run=run,
        rules=[(by_name[rule.name], rule) for rule in ordered],
        actuators=list(actuators),
        runtime=await _restore_runtime(session, run.id, seed_gates),
        rule_set_version=rule_set.fingerprint(),
    )
