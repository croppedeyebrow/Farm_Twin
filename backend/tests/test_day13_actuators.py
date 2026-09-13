"""
4단계 Day 13 — 가상 액추에이터·command/event 분리 테스트.

검증 축
-------
- HVAC/fan/dehumidifier/irrigation/LED 공통 apply API
- CommandDraft(목표) ≠ EventDraft(결과)
- START/STOP → APPLIED/STOPPED, 잘못된 목표 → REJECTED
- execute_decision: HOLD/SKIP 은 명령 없음
"""

from app.domain.control.actuators import (
    ActuatorSnapshot,
    ApplyOutcome,
    apply_for_all_types_demo,
    apply_start,
    apply_stop,
)
from app.domain.control.commands import (
    apply_command_draft,
    draft_command_from_decision,
    execute_decision,
)
from app.domain.control.evaluate import (
    MetricReading,
    RuleIntent,
    evaluate_rule,
)
from app.domain.control.schema import RuleDefinition
from app.domain.enums import (
    ActuatorMode,
    ActuatorType,
    ControlCommandStatus,
    ControlEventType,
    ReadingQuality,
    RuleComparator,
    SensorType,
)


def _cool_rule() -> RuleDefinition:
    return RuleDefinition(
        name="cool_on_high_temp",
        version=1,
        enabled=True,
        priority=10,
        metric=SensorType.TEMPERATURE,
        comparator=RuleComparator.GT,
        start_threshold=28.0,
        stop_threshold=25.0,
        target_actuator_type=ActuatorType.HVAC,
        target_mode=ActuatorMode.ON,
        target_output_ratio=0.8,
    )


def _hvac_off() -> ActuatorSnapshot:
    return ActuatorSnapshot(
        actuator_type=ActuatorType.HVAC,
        mode=ActuatorMode.OFF,
        output_ratio=0.0,
        code="hvac",
    )


def test_all_five_actuator_types_support_start() -> None:
    """HVAC/fan/dehumidifier/irrigation/LED 모두 START 적용 가능."""
    results = apply_for_all_types_demo()
    assert set(results) == set(ActuatorType)
    for actuator_type, result in results.items():
        assert result.outcome is ApplyOutcome.APPLIED
        assert result.after.mode is ActuatorMode.ON
        assert result.after.output_ratio == 0.7
        assert result.after.actuator_type is actuator_type


def test_apply_stop_clears_output() -> None:
    running = ActuatorSnapshot(
        actuator_type=ActuatorType.VENTILATION_FAN,
        mode=ActuatorMode.ON,
        output_ratio=1.0,
    )
    result = apply_stop(running)
    assert result.outcome is ApplyOutcome.STOPPED
    assert result.after.mode is ActuatorMode.OFF
    assert result.after.output_ratio == 0.0


def test_start_with_off_mode_rejected() -> None:
    result = apply_start(
        _hvac_off(),
        desired_mode=ActuatorMode.OFF,
        desired_output_ratio=0.5,
    )
    assert result.outcome is ApplyOutcome.REJECTED


def test_command_and_event_are_separate_objects() -> None:
    decision = evaluate_rule(
        _cool_rule(),
        reading=MetricReading(SensorType.TEMPERATURE, 30.0),
        actuator_active=False,
    )
    assert decision.intent is RuleIntent.START
    application = execute_decision(decision, _hvac_off(), simulation_time=100.0)
    assert application is not None
    # Command = 목표, Event = 결과 — 타입이 다름
    assert application.command.desired_mode is ActuatorMode.ON
    assert application.command.desired_output_ratio == 0.8
    assert application.command.status is ControlCommandStatus.SUCCEEDED
    assert application.event.event_type is ControlEventType.APPLIED
    assert application.event.actual_output_ratio == 0.8
    assert application.command is not application.event  # type: ignore[comparison-overlap]


def test_stop_decision_produces_stop_event() -> None:
    decision = evaluate_rule(
        _cool_rule(),
        reading=MetricReading(SensorType.TEMPERATURE, 24.0),
        actuator_active=True,
    )
    assert decision.intent is RuleIntent.STOP
    running = ActuatorSnapshot(
        actuator_type=ActuatorType.HVAC,
        mode=ActuatorMode.ON,
        output_ratio=0.8,
    )
    application = execute_decision(decision, running, simulation_time=200.0)
    assert application is not None
    assert application.command.desired_mode is ActuatorMode.OFF
    assert application.event.event_type is ControlEventType.STOPPED
    assert application.actuator_after.is_active is False


def test_hold_and_skip_produce_no_command() -> None:
    hold = evaluate_rule(
        _cool_rule(),
        reading=MetricReading(
            SensorType.TEMPERATURE,
            40.0,
            quality=ReadingQuality.SUSPECT,
        ),
        actuator_active=False,
    )
    assert draft_command_from_decision(hold, simulation_time=1.0) is None

    skip = evaluate_rule(
        _cool_rule(),
        reading=MetricReading(SensorType.TEMPERATURE, 20.0),
        actuator_active=False,
    )
    assert draft_command_from_decision(skip, simulation_time=1.0) is None


def test_type_mismatch_rejects_with_event() -> None:
    draft = draft_command_from_decision(
        evaluate_rule(
            _cool_rule(),
            reading=MetricReading(SensorType.TEMPERATURE, 30.0),
            actuator_active=False,
        ),
        simulation_time=50.0,
    )
    assert draft is not None
    led = ActuatorSnapshot(
        actuator_type=ActuatorType.LED,
        mode=ActuatorMode.OFF,
        output_ratio=0.0,
    )
    application = apply_command_draft(draft, led)
    assert application.event.event_type is ControlEventType.REJECTED
    assert application.command.status is ControlCommandStatus.CANCELLED


def test_irrigation_and_led_pipeline() -> None:
    """관수·LED 도 command→apply→event 경로가 동일하다."""
    irrigate = RuleDefinition(
        name="irrigate_on_dry",
        version=1,
        enabled=True,
        priority=20,
        metric=SensorType.SUBSTRATE_MOISTURE,
        comparator=RuleComparator.LT,
        start_threshold=30.0,
        stop_threshold=45.0,
        target_actuator_type=ActuatorType.IRRIGATION_PUMP,
        target_output_ratio=1.0,
    )
    decision = evaluate_rule(
        irrigate,
        reading=MetricReading(SensorType.SUBSTRATE_MOISTURE, 20.0),
        actuator_active=False,
    )
    pump = ActuatorSnapshot(
        actuator_type=ActuatorType.IRRIGATION_PUMP,
        mode=ActuatorMode.OFF,
        output_ratio=0.0,
    )
    app = execute_decision(decision, pump, simulation_time=10.0)
    assert app is not None
    assert app.event.event_type is ControlEventType.APPLIED

    led_rule = RuleDefinition(
        name="led_on_schedule_proxy",
        version=1,
        enabled=True,
        priority=30,
        metric=SensorType.PPFD,
        comparator=RuleComparator.LT,
        start_threshold=100.0,
        stop_threshold=700.0,
        target_actuator_type=ActuatorType.LED,
        target_output_ratio=1.0,
    )
    led_decision = evaluate_rule(
        led_rule,
        reading=MetricReading(SensorType.PPFD, 0.0),
        actuator_active=False,
    )
    led = ActuatorSnapshot(
        actuator_type=ActuatorType.LED,
        mode=ActuatorMode.OFF,
        output_ratio=0.0,
    )
    led_app = execute_decision(led_decision, led, simulation_time=11.0)
    assert led_app is not None
    assert led_app.actuator_after.mode is ActuatorMode.ON
