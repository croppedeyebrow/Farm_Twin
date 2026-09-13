"""
제어 게이트: min-on · cooldown · 자동/수동 (4단계 Day 14).

=============================================================================
왜 게이트가 필요한가
-----------------------------------------------------------------------------
히스테리시스만으로는 임계값 부근에서 매 스텝 START/STOP 이
번갈아 나갈 수 있다 (채터링).

  min_on_seconds   : START 시각 이후 최소 이 시간 동안 STOP 금지
  cooldown_seconds : STOP 시각 이후 최소 이 시간 동안 START 금지

시각은 **simulation_time** (가상 시계) 기준이다. wall-clock 이 아니다.

자동 / 수동
-----------
  AUTO   : 규칙 → 명령 허용
  MANUAL : 규칙 평가는 가능하나 START/STOP 을 SKIP 으로 강등
           (운영자가 설비를 수동 점유)

이 모듈은 RuleDecision 을 복사·강등할 뿐 Command 를 만들지 않는다.
Command/Event 는 commands.execute_decision 이 담당한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.control.evaluate import RuleDecision, RuleIntent
from app.domain.control.schema import RuleDefinition
from app.domain.enums import ActuatorType


class ControlMode(StrEnum):
    """재배실(또는 run) 제어 모드."""

    AUTO = "auto"
    MANUAL = "manual"


@dataclass
class ActuatorTimingState:
    """설비별 최근 START/STOP 가상 시각 (게이트 입력)."""

    last_start_sim_time: float | None = None
    last_stop_sim_time: float | None = None


@dataclass
class ControlRuntime:
    """
    게이트·idempotency 가 공유하는 가변 런타임.

    ClosedLoopRunner / step 루프가 한 인스턴스를 유지한다.
    accepted_keys 는 commands 모듈이 성공 적용 후 채운다.
    """

    mode: ControlMode = ControlMode.AUTO
    timing: dict[ActuatorType, ActuatorTimingState] = field(default_factory=dict)
    accepted_keys: set[str] = field(default_factory=set)

    def timing_for(self, actuator_type: ActuatorType) -> ActuatorTimingState:
        if actuator_type not in self.timing:
            self.timing[actuator_type] = ActuatorTimingState()
        return self.timing[actuator_type]

    def record_start(self, actuator_type: ActuatorType, simulation_time: float) -> None:
        self.timing_for(actuator_type).last_start_sim_time = simulation_time

    def record_stop(self, actuator_type: ActuatorType, simulation_time: float) -> None:
        self.timing_for(actuator_type).last_stop_sim_time = simulation_time


def apply_control_mode_gate(
    decision: RuleDecision,
    *,
    mode: ControlMode,
) -> RuleDecision:
    """MANUAL 이면 START/STOP → SKIP. HOLD 는 유지."""
    if mode is ControlMode.AUTO:
        return decision
    if decision.intent in (RuleIntent.START, RuleIntent.STOP):
        return RuleDecision(
            rule_name=decision.rule_name,
            rule_version=decision.rule_version,
            priority=decision.priority,
            intent=RuleIntent.SKIP,
            reason=f"manual mode blocks auto command ({decision.intent.value})",
            metric=decision.metric,
            metric_value=decision.metric_value,
            quality=decision.quality,
            target_actuator_type=decision.target_actuator_type,
            target_mode=decision.target_mode,
            target_output_ratio=decision.target_output_ratio,
        )
    return decision


def apply_timing_gates(
    decision: RuleDecision,
    rule: RuleDefinition,
    *,
    runtime: ControlRuntime,
    simulation_time: float,
) -> RuleDecision:
    """
    min_on / cooldown.

    STOP 후보이고 가동 경과 < min_on → SKIP
    START 후보이고 정지 경과 < cooldown → SKIP
    """
    if decision.intent not in (RuleIntent.START, RuleIntent.STOP):
        return decision

    timing = runtime.timing_for(decision.target_actuator_type)

    if (
        decision.intent is RuleIntent.STOP
        and rule.min_on_seconds > 0
        and timing.last_start_sim_time is not None
    ):
        elapsed = simulation_time - timing.last_start_sim_time
        if elapsed < rule.min_on_seconds:
            return RuleDecision(
                rule_name=decision.rule_name,
                rule_version=decision.rule_version,
                priority=decision.priority,
                intent=RuleIntent.SKIP,
                reason=(
                    f"min_on gate: elapsed={elapsed:.1f}s "
                    f"< min_on={rule.min_on_seconds:.1f}s"
                ),
                metric=decision.metric,
                metric_value=decision.metric_value,
                quality=decision.quality,
                target_actuator_type=decision.target_actuator_type,
                target_mode=decision.target_mode,
                target_output_ratio=decision.target_output_ratio,
            )

    if (
        decision.intent is RuleIntent.START
        and rule.cooldown_seconds > 0
        and timing.last_stop_sim_time is not None
    ):
        elapsed = simulation_time - timing.last_stop_sim_time
        if elapsed < rule.cooldown_seconds:
            return RuleDecision(
                rule_name=decision.rule_name,
                rule_version=decision.rule_version,
                priority=decision.priority,
                intent=RuleIntent.SKIP,
                reason=(
                    f"cooldown gate: elapsed={elapsed:.1f}s "
                    f"< cooldown={rule.cooldown_seconds:.1f}s"
                ),
                metric=decision.metric,
                metric_value=decision.metric_value,
                quality=decision.quality,
                target_actuator_type=decision.target_actuator_type,
                target_mode=decision.target_mode,
                target_output_ratio=decision.target_output_ratio,
            )

    return decision


def gate_decision(
    decision: RuleDecision,
    rule: RuleDefinition,
    *,
    runtime: ControlRuntime,
    simulation_time: float,
) -> RuleDecision:
    """모드 게이트 → 타이밍 게이트 순 적용."""
    after_mode = apply_control_mode_gate(decision, mode=runtime.mode)
    return apply_timing_gates(
        after_mode,
        rule,
        runtime=runtime,
        simulation_time=simulation_time,
    )


def find_rule(
    rule_set_rules: tuple[RuleDefinition, ...],
    name: str,
) -> RuleDefinition | None:
    """이름으로 규칙 조회 (loop 등에서 게이트용)."""
    for rule in rule_set_rules:
        if rule.name == name:
            return rule
    return None
