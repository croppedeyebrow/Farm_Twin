"""
4단계 Day 12 — 규칙 schema·연산자·우선순위·품질 정책 테스트.

검증 축
-------
- RULE_SCHEMA_VERSION / RuleDefinition.version 계약
- GT/GTE/LT/LTE 비교
- 히스테리시스 START/STOP/HOLD
- 동일 액추에이터 충돌 시 priority(작을수록 승)
- ReadingQuality → USE / HOLD / REJECT (quality policy)
"""

import pytest

from app.domain.control.evaluate import (
    MetricReading,
    RuleIntent,
    compare,
    evaluate_rule,
    evaluate_ruleset,
)
from app.domain.control.quality import (
    DEFAULT_QUALITY_POLICY,
    QualityAction,
    QualityPolicy,
)
from app.domain.control.schema import (
    RULE_SCHEMA_VERSION,
    RuleDefinition,
    RuleSet,
)
from app.domain.enums import (
    ActuatorMode,
    ActuatorType,
    ReadingQuality,
    RuleComparator,
    SensorType,
)


def _cool_rule(**overrides: object) -> RuleDefinition:
    data: dict = {
        "name": "cool_on_high_temp",
        "version": 1,
        "enabled": True,
        "priority": 10,
        "metric": SensorType.TEMPERATURE,
        "comparator": RuleComparator.GT,
        "start_threshold": 28.0,
        "stop_threshold": 25.0,
        "target_actuator_type": ActuatorType.HVAC,
        "target_mode": ActuatorMode.ON,
        "target_output_ratio": 0.8,
    }
    data.update(overrides)
    return RuleDefinition(**data)  # type: ignore[arg-type]


def test_rule_schema_version_constant() -> None:
    assert RULE_SCHEMA_VERSION == "rules.v1"
    rule_set = RuleSet(rules=(_cool_rule(),))
    assert rule_set.schema_version == RULE_SCHEMA_VERSION


def test_rule_definition_rejects_invalid_version() -> None:
    with pytest.raises(ValueError):
        _cool_rule(version=0)


def test_compare_operators() -> None:
    assert compare(29.0, RuleComparator.GT, 28.0) is True
    assert compare(28.0, RuleComparator.GT, 28.0) is False
    assert compare(28.0, RuleComparator.GTE, 28.0) is True
    assert compare(20.0, RuleComparator.LT, 25.0) is True
    assert compare(25.0, RuleComparator.LTE, 25.0) is True


def test_start_when_above_threshold() -> None:
    decision = evaluate_rule(
        _cool_rule(),
        reading=MetricReading(SensorType.TEMPERATURE, 29.0),
        actuator_active=False,
    )
    assert decision.intent is RuleIntent.START
    assert decision.rule_version == 1


def test_stop_when_active_and_below_stop_threshold() -> None:
    decision = evaluate_rule(
        _cool_rule(),
        reading=MetricReading(SensorType.TEMPERATURE, 24.0),
        actuator_active=True,
    )
    assert decision.intent is RuleIntent.STOP


def test_hysteresis_band_keeps_running() -> None:
    """25 < T <= 28 이고 이미 ON 이면 STOP도 START도 아님."""
    decision = evaluate_rule(
        _cool_rule(),
        reading=MetricReading(SensorType.TEMPERATURE, 26.5),
        actuator_active=True,
    )
    assert decision.intent is RuleIntent.SKIP
    assert "keep running" in decision.reason


def test_quality_bad_is_rejected() -> None:
    decision = evaluate_rule(
        _cool_rule(),
        reading=MetricReading(
            SensorType.TEMPERATURE,
            40.0,
            quality=ReadingQuality.BAD,
        ),
        actuator_active=False,
    )
    assert decision.intent is RuleIntent.SKIP
    assert "rejected" in decision.reason


def test_quality_suspect_holds_by_default() -> None:
    decision = evaluate_rule(
        _cool_rule(),
        reading=MetricReading(
            SensorType.TEMPERATURE,
            40.0,
            quality=ReadingQuality.SUSPECT,
        ),
        actuator_active=False,
    )
    assert decision.intent is RuleIntent.HOLD
    assert DEFAULT_QUALITY_POLICY.action_for(ReadingQuality.SUSPECT) is QualityAction.HOLD


def test_quality_policy_can_allow_suspect() -> None:
    policy = QualityPolicy(suspect=QualityAction.USE)
    decision = evaluate_rule(
        _cool_rule(),
        reading=MetricReading(
            SensorType.TEMPERATURE,
            40.0,
            quality=ReadingQuality.SUSPECT,
        ),
        actuator_active=False,
        quality_policy=policy,
    )
    assert decision.intent is RuleIntent.START


def test_priority_lower_number_wins_on_same_actuator() -> None:
    """동일 HVAC 를 겨냥한 규칙 중 priority 작은 쪽만 채택."""
    high = _cool_rule(name="urgent", priority=5, start_threshold=27.0)
    low = _cool_rule(name="normal", priority=50, start_threshold=30.0)
    rule_set = RuleSet(rules=(low, high))  # 입력 순서는 달라도 OK
    decisions = evaluate_ruleset(
        rule_set,
        readings={
            SensorType.TEMPERATURE: MetricReading(SensorType.TEMPERATURE, 28.5),
        },
    )
    assert len(decisions) == 1
    assert decisions[0].rule_name == "urgent"
    assert decisions[0].intent is RuleIntent.START


def test_disabled_rule_skipped() -> None:
    decision = evaluate_rule(
        _cool_rule(enabled=False),
        reading=MetricReading(SensorType.TEMPERATURE, 40.0),
        actuator_active=False,
    )
    assert decision.intent is RuleIntent.SKIP


def test_enabled_by_priority_sort() -> None:
    rule_set = RuleSet(
        rules=(
            _cool_rule(name="b", priority=20),
            _cool_rule(name="a", priority=10),
        )
    )
    ordered = rule_set.enabled_by_priority()
    assert [rule.name for rule in ordered] == ["a", "b"]


def test_lt_comparator_irrigation_style() -> None:
    """배지수분 부족 시 관수: LT start."""
    rule = RuleDefinition(
        name="irrigate_on_dry",
        version=1,
        enabled=True,
        priority=20,
        metric=SensorType.SUBSTRATE_MOISTURE,
        comparator=RuleComparator.LT,
        start_threshold=30.0,
        stop_threshold=45.0,
        target_actuator_type=ActuatorType.IRRIGATION_PUMP,
    )
    start = evaluate_rule(
        rule,
        reading=MetricReading(SensorType.SUBSTRATE_MOISTURE, 25.0),
        actuator_active=False,
    )
    assert start.intent is RuleIntent.START
    stop = evaluate_rule(
        rule,
        reading=MetricReading(SensorType.SUBSTRATE_MOISTURE, 50.0),
        actuator_active=True,
    )
    assert stop.intent is RuleIntent.STOP
