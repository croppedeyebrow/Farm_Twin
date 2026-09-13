"""
4단계 Day 14 — min-on·cooldown·자동/수동·idempotency 테스트.

검증 축
-------
- min_on: START 직후 STOP → SKIP
- cooldown: STOP 직후 START → SKIP
- MANUAL: START/STOP → SKIP (HOLD 유지)
- idempotency_key: 동일 START 재발행 억제, STOP 후 START 키 재허용
시각은 simulation_time (가상 시계) 기준.
"""

from app.domain.control.actuators import ActuatorSnapshot
from app.domain.control.commands import execute_decision
from app.domain.control.evaluate import (
    MetricReading,
    RuleIntent,
    evaluate_rule,
)
from app.domain.control.gates import (
    ControlMode,
    ControlRuntime,
    apply_timing_gates,
    gate_decision,
)
from app.domain.control.schema import RuleDefinition
from app.domain.enums import (
    ActuatorMode,
    ActuatorType,
    ControlEventType,
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
        "cooldown_seconds": 30.0,
        "min_on_seconds": 60.0,
    }
    data.update(overrides)
    return RuleDefinition(**data)  # type: ignore[arg-type]


def _hvac(active: bool = False) -> ActuatorSnapshot:
    if active:
        return ActuatorSnapshot(
            actuator_type=ActuatorType.HVAC,
            mode=ActuatorMode.ON,
            output_ratio=0.8,
        )
    return ActuatorSnapshot(
        actuator_type=ActuatorType.HVAC,
        mode=ActuatorMode.OFF,
        output_ratio=0.0,
    )


def test_min_on_blocks_early_stop() -> None:
    rule = _cool_rule(min_on_seconds=60.0)
    runtime = ControlRuntime()
    runtime.record_start(ActuatorType.HVAC, 100.0)

    stop = evaluate_rule(
        rule,
        reading=MetricReading(SensorType.TEMPERATURE, 24.0),
        actuator_active=True,
    )
    assert stop.intent is RuleIntent.STOP

    gated = apply_timing_gates(
        stop,
        rule,
        runtime=runtime,
        simulation_time=130.0,  # 30s < 60s min_on
    )
    assert gated.intent is RuleIntent.SKIP
    assert "min_on" in gated.reason

    ok = apply_timing_gates(
        stop,
        rule,
        runtime=runtime,
        simulation_time=170.0,  # 70s >= 60s
    )
    assert ok.intent is RuleIntent.STOP


def test_cooldown_blocks_early_restart() -> None:
    rule = _cool_rule(cooldown_seconds=30.0)
    runtime = ControlRuntime()
    runtime.record_stop(ActuatorType.HVAC, 200.0)

    start = evaluate_rule(
        rule,
        reading=MetricReading(SensorType.TEMPERATURE, 30.0),
        actuator_active=False,
    )
    blocked = apply_timing_gates(
        start,
        rule,
        runtime=runtime,
        simulation_time=220.0,  # 20s < 30s
    )
    assert blocked.intent is RuleIntent.SKIP
    assert "cooldown" in blocked.reason

    allowed = apply_timing_gates(
        start,
        rule,
        runtime=runtime,
        simulation_time=240.0,
    )
    assert allowed.intent is RuleIntent.START


def test_manual_mode_blocks_auto_commands() -> None:
    rule = _cool_rule()
    runtime = ControlRuntime(mode=ControlMode.MANUAL)
    start = evaluate_rule(
        rule,
        reading=MetricReading(SensorType.TEMPERATURE, 30.0),
        actuator_active=False,
    )
    gated = gate_decision(start, rule, runtime=runtime, simulation_time=0.0)
    assert gated.intent is RuleIntent.SKIP
    assert "manual" in gated.reason

    app = execute_decision(
        start,
        _hvac(),
        simulation_time=0.0,
        rule=rule,
        runtime=runtime,
    )
    assert app is None


def test_idempotency_suppresses_duplicate_start() -> None:
    """같은 START 목표가 매 스텝 나가지 않는다."""
    rule = _cool_rule(min_on_seconds=0.0, cooldown_seconds=0.0)
    runtime = ControlRuntime()
    decision = evaluate_rule(
        rule,
        reading=MetricReading(SensorType.TEMPERATURE, 30.0),
        actuator_active=False,
    )

    first = execute_decision(
        decision,
        _hvac(),
        simulation_time=10.0,
        rule=rule,
        runtime=runtime,
    )
    assert first is not None
    assert first.event.event_type is ControlEventType.APPLIED

    # 이미 ON 인데 규칙이 또 START 를 내면 (또는 동일 키) 억제
    second = execute_decision(
        decision,
        first.actuator_after,
        simulation_time=20.0,
        rule=rule,
        runtime=runtime,
    )
    assert second is None
    assert first.command.idempotency_key in runtime.accepted_keys


def test_after_stop_can_start_again_with_new_cycle() -> None:
    rule = _cool_rule(min_on_seconds=0.0, cooldown_seconds=0.0)
    runtime = ControlRuntime()

    start = evaluate_rule(
        rule,
        reading=MetricReading(SensorType.TEMPERATURE, 30.0),
        actuator_active=False,
    )
    on = execute_decision(
        start,
        _hvac(),
        simulation_time=0.0,
        rule=rule,
        runtime=runtime,
    )
    assert on is not None

    stop = evaluate_rule(
        rule,
        reading=MetricReading(SensorType.TEMPERATURE, 24.0),
        actuator_active=True,
    )
    off = execute_decision(
        stop,
        on.actuator_after,
        simulation_time=100.0,
        rule=rule,
        runtime=runtime,
    )
    assert off is not None
    assert off.event.event_type is ControlEventType.STOPPED

    # START 키가 지워져 다시 START 가능
    again = execute_decision(
        start,
        off.actuator_after,
        simulation_time=200.0,
        rule=rule,
        runtime=runtime,
    )
    assert again is not None
    assert again.event.event_type is ControlEventType.APPLIED


def test_auto_mode_allows_pipeline() -> None:
    rule = _cool_rule(min_on_seconds=0.0, cooldown_seconds=0.0)
    runtime = ControlRuntime(mode=ControlMode.AUTO)
    decision = evaluate_rule(
        rule,
        reading=MetricReading(SensorType.TEMPERATURE, 29.0),
        actuator_active=False,
    )
    app = execute_decision(
        decision,
        _hvac(),
        simulation_time=1.0,
        rule=rule,
        runtime=runtime,
    )
    assert app is not None
    assert runtime.timing_for(ActuatorType.HVAC).last_start_sim_time == 1.0
