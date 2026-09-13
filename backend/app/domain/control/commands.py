"""
ControlCommand / ControlEvent 도메인 (4단계 Day 13~14).

=============================================================================
불변조건 (DB 모델과 동일)
-----------------------------------------------------------------------------
- Command = 목표 (desired_mode, desired_output_ratio)
- Event   = 적용 결과 (APPLIED / STOPPED / FAILED / REJECTED)
- 한 테이블에 합치지 않는다. Command 행을 Event 로 덮어쓰지 않는다.

idempotency (Day 14)
--------------------
키 형식:
  {run}:{rule}:v{version}:{intent}:{mode}:{ratio:.3f}

- sim_time 을 넣지 않는다 (넣으면 매 스텝 키가 달라져 중복 억제 실패).
- 성공한 START 키를 등록하면, 같은 START 가 매 스텝 나가지 않는다.
- STOP 성공 시 START 계열 키를 지워 다음 사이클 START 를 허용 (반대도 동일).
- min-on / cooldown / MANUAL 은 gates 에서 결정 강등 후 여기로 온다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.control.actuators import (
    ActuatorApplyResult,
    ActuatorSnapshot,
    ApplyOutcome,
    apply_start,
    apply_stop,
)
from app.domain.control.evaluate import RuleDecision, RuleIntent
from app.domain.control.gates import ControlRuntime
from app.domain.control.schema import RuleDefinition
from app.domain.enums import (
    ActuatorMode,
    ActuatorType,
    ControlCommandStatus,
    ControlEventType,
)


@dataclass(frozen=True)
class CommandDraft:
    """DB ControlCommand 투영 전 도메인 초안."""

    actuator_type: ActuatorType
    desired_mode: ActuatorMode
    desired_output_ratio: float
    simulation_time: float
    reason: str
    rule_name: str
    rule_version: int
    idempotency_key: str
    status: ControlCommandStatus = ControlCommandStatus.PENDING


@dataclass(frozen=True)
class EventDraft:
    """DB ControlEvent 초안. command 와 1:N."""

    event_type: ControlEventType
    actual_output_ratio: float | None
    message: str
    simulation_time: float


@dataclass(frozen=True)
class CommandApplication:
    """한 번의 명령 수명: draft → 적용 → event (+ 갱신된 설비 스냅샷)."""

    command: CommandDraft
    event: EventDraft
    actuator_after: ActuatorSnapshot
    apply: ActuatorApplyResult
    duplicate_suppressed: bool = False


def build_idempotency_key(
    *,
    run_key: str,
    rule_name: str,
    rule_version: int,
    intent: RuleIntent,
    desired_mode: ActuatorMode,
    desired_output_ratio: float,
) -> str:
    """
    동일 규칙·의도·목표면 같은 키.

    sim_time 을 넣지 않는다 — 매 스텝마다 키가 바뀌면 idempotency 가 무의미해진다.
    """
    return (
        f"{run_key}:{rule_name}:v{rule_version}:"
        f"{intent.value}:{desired_mode.value}:{desired_output_ratio:.3f}"
    )


def _clear_opposite_keys(
    runtime: ControlRuntime,
    *,
    run_key: str,
    rule_name: str,
    rule_version: int,
    intent: RuleIntent,
) -> None:
    """반대 의도 키를 지워 다음 사이클에서 새 명령을 허용한다."""
    opposite = RuleIntent.STOP if intent is RuleIntent.START else RuleIntent.START
    prefix = f"{run_key}:{rule_name}:v{rule_version}:{opposite.value}:"
    runtime.accepted_keys = {
        key for key in runtime.accepted_keys if not key.startswith(prefix)
    }


def draft_command_from_decision(
    decision: RuleDecision,
    *,
    simulation_time: float,
    run_key: str = "run",
    runtime: ControlRuntime | None = None,
) -> CommandDraft | None:
    """
    RuleDecision → CommandDraft.

    HOLD/SKIP 은 명령 없음.
    runtime 이 있으면 idempotency: 이미 수락된 키면 None (중복 억제).
    """
    if decision.intent is RuleIntent.HOLD or decision.intent is RuleIntent.SKIP:
        return None

    if decision.intent is RuleIntent.START:
        mode = decision.target_mode
        ratio = decision.target_output_ratio
    elif decision.intent is RuleIntent.STOP:
        mode = ActuatorMode.OFF
        ratio = 0.0
    else:
        return None

    key = build_idempotency_key(
        run_key=run_key,
        rule_name=decision.rule_name,
        rule_version=decision.rule_version,
        intent=decision.intent,
        desired_mode=mode,
        desired_output_ratio=ratio,
    )

    if runtime is not None and key in runtime.accepted_keys:
        return None

    return CommandDraft(
        actuator_type=decision.target_actuator_type,
        desired_mode=mode,
        desired_output_ratio=ratio,
        simulation_time=simulation_time,
        reason=decision.reason,
        rule_name=decision.rule_name,
        rule_version=decision.rule_version,
        idempotency_key=key,
    )


def _outcome_to_event_type(outcome: ApplyOutcome) -> ControlEventType:
    return {
        ApplyOutcome.APPLIED: ControlEventType.APPLIED,
        ApplyOutcome.STOPPED: ControlEventType.STOPPED,
        ApplyOutcome.REJECTED: ControlEventType.REJECTED,
        ApplyOutcome.FAILED: ControlEventType.FAILED,
    }[outcome]


def _command_status_after(outcome: ApplyOutcome) -> ControlCommandStatus:
    if outcome in (ApplyOutcome.APPLIED, ApplyOutcome.STOPPED):
        return ControlCommandStatus.SUCCEEDED
    if outcome is ApplyOutcome.REJECTED:
        return ControlCommandStatus.CANCELLED
    return ControlCommandStatus.FAILED


def apply_command_draft(
    command: CommandDraft,
    current: ActuatorSnapshot,
    *,
    runtime: ControlRuntime | None = None,
    run_key: str = "run",
    intent: RuleIntent | None = None,
) -> CommandApplication:
    """
    Command(목표)를 가상 액추에이터에 적용하고 Event(결과)를 만든다.

    성공 시 runtime 에 idempotency_key 등록 + 타이밍 기록.
    """
    if current.actuator_type is not command.actuator_type:
        apply = ActuatorApplyResult(
            before=current,
            after=current,
            outcome=ApplyOutcome.REJECTED,
            message=(
                f"type mismatch: command={command.actuator_type.value} "
                f"actuator={current.actuator_type.value}"
            ),
        )
    elif command.desired_mode is ActuatorMode.OFF:
        apply = apply_stop(current)
    else:
        apply = apply_start(
            current,
            desired_mode=command.desired_mode,
            desired_output_ratio=command.desired_output_ratio,
        )

    event = EventDraft(
        event_type=_outcome_to_event_type(apply.outcome),
        actual_output_ratio=apply.after.output_ratio,
        message=apply.message,
        simulation_time=command.simulation_time,
    )
    updated_command = CommandDraft(
        actuator_type=command.actuator_type,
        desired_mode=command.desired_mode,
        desired_output_ratio=command.desired_output_ratio,
        simulation_time=command.simulation_time,
        reason=command.reason,
        rule_name=command.rule_name,
        rule_version=command.rule_version,
        idempotency_key=command.idempotency_key,
        status=_command_status_after(apply.outcome),
    )

    if (
        runtime is not None
        and apply.outcome in (ApplyOutcome.APPLIED, ApplyOutcome.STOPPED)
    ):
        inferred = (
            intent
            if intent is not None
            else (
                RuleIntent.STOP
                if command.desired_mode is ActuatorMode.OFF
                else RuleIntent.START
            )
        )
        runtime.accepted_keys.add(command.idempotency_key)
        _clear_opposite_keys(
            runtime,
            run_key=run_key,
            rule_name=command.rule_name,
            rule_version=command.rule_version,
            intent=inferred,
        )
        if inferred is RuleIntent.START:
            runtime.record_start(command.actuator_type, command.simulation_time)
        else:
            runtime.record_stop(command.actuator_type, command.simulation_time)

    return CommandApplication(
        command=updated_command,
        event=event,
        actuator_after=apply.after,
        apply=apply,
    )


def execute_decision(
    decision: RuleDecision,
    current: ActuatorSnapshot,
    *,
    simulation_time: float,
    run_key: str = "run",
    rule: RuleDefinition | None = None,
    runtime: ControlRuntime | None = None,
) -> CommandApplication | None:
    """
    (옵션) 게이트 → 명령 초안 → idempotency → 적용 → 이벤트.

    rule+runtime 이 있으면 Day 14 게이트를 먼저 적용한다.
    """
    gated = decision
    if rule is not None and runtime is not None:
        from app.domain.control.gates import gate_decision

        gated = gate_decision(
            decision,
            rule,
            runtime=runtime,
            simulation_time=simulation_time,
        )

    draft = draft_command_from_decision(
        gated,
        simulation_time=simulation_time,
        run_key=run_key,
        runtime=runtime,
    )
    if draft is None:
        return None

    return apply_command_draft(
        draft,
        current,
        runtime=runtime,
        run_key=run_key,
        intent=gated.intent,
    )


def wall_clock_now() -> datetime:
    """테스트/서비스에서 issued_at·recorded_at 채울 때 사용 (UTC 권장)."""
    from datetime import UTC

    return datetime.now(UTC)
