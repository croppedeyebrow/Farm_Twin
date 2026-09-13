"""
규칙 조건 평가 · 우선순위 해석 (4단계 Day 12).

=============================================================================
입력 → 출력
-----------------------------------------------------------------------------
입력
  - RuleSet (schema + versioned rules)
  - MetricReading: 센서 타입별 최신 측정(값·품질)
  - actuator_active: 해당 설비가 지금 ON 인지 (히스테리시스 분기)

출력
  - RuleDecision (START / STOP / HOLD / SKIP)
  - evaluate_ruleset: actuator 당 우선순위 승리 결정만

이후 단계
---------
Day 13: commands + actuators 로 Command/Event 분리 적용
Day 14: gates (min-on/cooldown/MANUAL) + idempotency
Day 15: loop.ClosedLoopRunner 가 환경 모델과 연결

히스테리시스
------------
active=False → start_threshold 만 평가 (START?)
active=True  → stop_threshold 만 평가 (STOP?)
둘 다 아니면 SKIP ("keep running" / "start not met")
→ 임계값 한 점에서 ON/OFF 가 떨리는 것을 1차로 줄인다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.control.quality import (
    DEFAULT_QUALITY_POLICY,
    QualityAction,
    QualityPolicy,
)
from app.domain.control.schema import RuleDefinition, RuleSet
from app.domain.enums import (
    ActuatorMode,
    ActuatorType,
    ReadingQuality,
    RuleComparator,
    SensorType,
)


class RuleIntent(StrEnum):
    """규칙이 이번 스텝에 원하는 행동 (아직 DB 명령 아님)."""

    START = "start"
    STOP = "stop"
    HOLD = "hold"
    SKIP = "skip"


@dataclass(frozen=True)
class MetricReading:
    """규칙 입력용 한 메트릭 측정."""

    sensor_type: SensorType
    value: float
    quality: ReadingQuality = ReadingQuality.GOOD


@dataclass(frozen=True)
class RuleDecision:
    """한 규칙 판정 결과. commands.execute_decision 의 입력."""

    rule_name: str
    rule_version: int
    priority: int
    intent: RuleIntent
    reason: str
    metric: SensorType
    metric_value: float | None
    quality: ReadingQuality | None
    target_actuator_type: ActuatorType
    target_mode: ActuatorMode
    target_output_ratio: float


def compare(value: float, comparator: RuleComparator, threshold: float) -> bool:
    """조건 연산자 평가 (GT/GTE/LT/LTE)."""
    if comparator is RuleComparator.GT:
        return value > threshold
    if comparator is RuleComparator.GTE:
        return value >= threshold
    if comparator is RuleComparator.LT:
        return value < threshold
    if comparator is RuleComparator.LTE:
        return value <= threshold
    raise ValueError(f"unknown comparator: {comparator}")


def _stop_condition(
    value: float,
    comparator: RuleComparator,
    stop_threshold: float,
) -> bool:
    """
    정지 조건 = start 비교의 반대쪽 경계.

    GT/GTE 로 시작 → 값 <= stop 이면 정지
    LT/LTE 로 시작 → 값 >= stop 이면 정지
    """
    if comparator in (RuleComparator.GT, RuleComparator.GTE):
        return value <= stop_threshold
    return value >= stop_threshold


def evaluate_rule(
    rule: RuleDefinition,
    *,
    reading: MetricReading | None,
    actuator_active: bool,
    quality_policy: QualityPolicy = DEFAULT_QUALITY_POLICY,
) -> RuleDecision:
    """
    단일 규칙 평가 (게이트·idempotency 이전).

    품질 REJECT → SKIP, HOLD → HOLD.
    그 다음 히스테리시스 START/STOP/SKIP.
    """
    base = {
        "rule_name": rule.name,
        "rule_version": rule.version,
        "priority": rule.priority,
        "metric": rule.metric,
        "target_actuator_type": rule.target_actuator_type,
        "target_mode": rule.target_mode,
        "target_output_ratio": rule.target_output_ratio,
    }

    if not rule.enabled:
        return RuleDecision(
            intent=RuleIntent.SKIP,
            reason="rule disabled",
            metric_value=None,
            quality=None,
            **base,
        )

    if reading is None:
        return RuleDecision(
            intent=RuleIntent.SKIP,
            reason="no reading for metric",
            metric_value=None,
            quality=None,
            **base,
        )

    action = quality_policy.action_for(reading.quality)
    if action is QualityAction.REJECT:
        return RuleDecision(
            intent=RuleIntent.SKIP,
            reason=f"quality rejected: {reading.quality.value}",
            metric_value=reading.value,
            quality=reading.quality,
            **base,
        )
    if action is QualityAction.HOLD:
        return RuleDecision(
            intent=RuleIntent.HOLD,
            reason=f"quality hold: {reading.quality.value}",
            metric_value=reading.value,
            quality=reading.quality,
            **base,
        )

    if actuator_active:
        if _stop_condition(reading.value, rule.comparator, rule.stop_threshold):
            return RuleDecision(
                intent=RuleIntent.STOP,
                reason=(
                    f"stop: value={reading.value} vs stop_threshold="
                    f"{rule.stop_threshold} ({rule.comparator.value})"
                ),
                metric_value=reading.value,
                quality=reading.quality,
                **base,
            )
        return RuleDecision(
            intent=RuleIntent.SKIP,
            reason="active but stop threshold not met — keep running",
            metric_value=reading.value,
            quality=reading.quality,
            **base,
        )

    if compare(reading.value, rule.comparator, rule.start_threshold):
        return RuleDecision(
            intent=RuleIntent.START,
            reason=(
                f"start: value={reading.value} {rule.comparator.value} "
                f"{rule.start_threshold}"
            ),
            metric_value=reading.value,
            quality=reading.quality,
            **base,
        )

    return RuleDecision(
        intent=RuleIntent.SKIP,
        reason="start threshold not met",
        metric_value=reading.value,
        quality=reading.quality,
        **base,
    )


def evaluate_ruleset(
    rule_set: RuleSet,
    *,
    readings: dict[SensorType, MetricReading],
    active_actuators: set[ActuatorType] | None = None,
    quality_policy: QualityPolicy = DEFAULT_QUALITY_POLICY,
) -> list[RuleDecision]:
    """
    규칙 집합 평가 + 액추에이터별 우선순위 충돌 해소.

    enabled_by_priority 순으로 순회하므로 먼저 온 결정이 승리.
    SKIP 은 반환에서 제외 (감사 로그가 필요하면 호출측에서 evaluate_rule 사용).
    """
    active = active_actuators or set()
    ordered = rule_set.enabled_by_priority()
    winners: dict[ActuatorType, RuleDecision] = {}

    for rule in ordered:
        decision = evaluate_rule(
            rule,
            reading=readings.get(rule.metric),
            actuator_active=rule.target_actuator_type in active,
            quality_policy=quality_policy,
        )
        if decision.intent is RuleIntent.SKIP:
            continue
        if rule.target_actuator_type in winners:
            continue
        winners[rule.target_actuator_type] = decision

    return sorted(winners.values(), key=lambda item: (item.priority, item.rule_name))
