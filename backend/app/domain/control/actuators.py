"""
가상 액추에이터 상태·적용 (4단계 Day 13).

=============================================================================
역할
-----------------------------------------------------------------------------
RuleDecision(START/STOP) → 설비에 **목표**를 적용하고,
실제 반영된 mode/output 을 돌려준다.

MVP: HVAC / fan / dehumidifier / irrigation / LED 는
동일한 (mode, output_ratio∈[0,1]) 인터페이스.
종류별 **물리 효과**는 environment.step_* 의 ActuatorInputs 가 담당.
이 모듈은 "명령이 설비 상태를 바꿨는가"만 본다.

Command vs ApplyOutcome
-----------------------
- Command 는 "무엇을 원하는가"
- ApplyOutcome / Event 는 "무엇이 되었는가"
실패·거부여도 Command 감사 이력은 남기고 Event 로 결과를 남긴다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.enums import ActuatorMode, ActuatorType


class ApplyOutcome(StrEnum):
    """액추에이터 적용 결과 → ControlEventType 으로 투영."""

    APPLIED = "applied"
    STOPPED = "stopped"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True)
class ActuatorSnapshot:
    """설비 현재 운전 스냅샷 (도메인, ORM Actuator 캐시와 대응)."""

    actuator_type: ActuatorType
    mode: ActuatorMode
    output_ratio: float
    code: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.output_ratio <= 1.0:
            raise ValueError("output_ratio must be in [0, 1]")

    @property
    def is_active(self) -> bool:
        """히스테리시스용: OFF 가 아니고 출력이 있으면 가동 중."""
        return self.mode is not ActuatorMode.OFF and self.output_ratio > 0.0


@dataclass(frozen=True)
class ActuatorApplyResult:
    """적용 전후 스냅샷 + 결과 코드."""

    before: ActuatorSnapshot
    after: ActuatorSnapshot
    outcome: ApplyOutcome
    message: str


def apply_start(
    current: ActuatorSnapshot,
    *,
    desired_mode: ActuatorMode,
    desired_output_ratio: float,
) -> ActuatorApplyResult:
    """
    START: 목표 mode/output 으로 켠다.

    desired_mode=OFF 이거나 ratio 범위 밖이면 REJECTED (상태 불변).
    """
    if desired_mode is ActuatorMode.OFF:
        return ActuatorApplyResult(
            before=current,
            after=current,
            outcome=ApplyOutcome.REJECTED,
            message="START requires non-OFF desired_mode",
        )
    if not 0.0 <= desired_output_ratio <= 1.0:
        return ActuatorApplyResult(
            before=current,
            after=current,
            outcome=ApplyOutcome.REJECTED,
            message="desired_output_ratio out of range",
        )

    after = ActuatorSnapshot(
        actuator_type=current.actuator_type,
        mode=desired_mode,
        output_ratio=desired_output_ratio,
        code=current.code,
    )
    return ActuatorApplyResult(
        before=current,
        after=after,
        outcome=ApplyOutcome.APPLIED,
        message=(
            f"{current.actuator_type.value} "
            f"{current.mode.value}/{current.output_ratio:.2f} "
            f"→ {after.mode.value}/{after.output_ratio:.2f}"
        ),
    )


def apply_stop(current: ActuatorSnapshot) -> ActuatorApplyResult:
    """STOP: mode=OFF, output=0."""
    after = ActuatorSnapshot(
        actuator_type=current.actuator_type,
        mode=ActuatorMode.OFF,
        output_ratio=0.0,
        code=current.code,
    )
    return ActuatorApplyResult(
        before=current,
        after=after,
        outcome=ApplyOutcome.STOPPED,
        message=f"{current.actuator_type.value} stopped",
    )


def apply_for_all_types_demo() -> dict[ActuatorType, ActuatorApplyResult]:
    """다섯 설비 타입이 동일 apply API 를 쓰는지 확인하는 헬퍼."""
    results: dict[ActuatorType, ActuatorApplyResult] = {}
    for actuator_type in ActuatorType:
        current = ActuatorSnapshot(
            actuator_type=actuator_type,
            mode=ActuatorMode.OFF,
            output_ratio=0.0,
            code=actuator_type.value,
        )
        results[actuator_type] = apply_start(
            current,
            desired_mode=ActuatorMode.ON,
            desired_output_ratio=0.7,
        )
    return results
