"""
4단계 Day 15 — 폐쇄 루프 통합·채터링·중복·충돌 테스트.

ClosedLoopRunner 로 UI 없이 증명한다.

필수 증거
---------
온도 상승 → 냉방 명령 → HVAC ON → 온도 하락 → stop 임계 → 냉방 정지
(고온 외기로 START 유도 후, 외기를 완화해 STOP 이 가능하도록 함)

추가
----
- 배지수분 부족 → 관수 → 수분 상승 → 정지
- 동일 START 중복 억제 (idempotency)
- min-on/cooldown 으로 임계값 부근 채터링 완화
- 동일 액추에이터 규칙 충돌 시 우선순위 승리
"""

from app.domain.control.evaluate import RuleIntent, evaluate_ruleset
from app.domain.control.gates import ControlMode, ControlRuntime
from app.domain.control.loop import ClosedLoopRunner
from app.domain.control.schema import RuleDefinition, RuleSet
from app.domain.enums import (
    ActuatorMode,
    ActuatorType,
    ControlEventType,
    RuleComparator,
    SensorType,
)
from app.domain.simulation.params import EnvironmentModelParams
from app.domain.simulation.state import (
    EnvironmentState,
    InitialEnvironmentState,
    OutdoorCondition,
)


def _outdoor_hot() -> OutdoorCondition:
    """실내를 데우는 고정 외기 (누설로 온도 상승 유도)."""
    return OutdoorCondition(
        temperature_c=40.0,
        humidity_pct=40.0,
        simulation_time=0.0,
        source="SYNTHETIC",
        co2_ppm=420.0,
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
        "target_output_ratio": 1.0,
        "cooldown_seconds": 60.0,
        "min_on_seconds": 120.0,
    }
    data.update(overrides)
    return RuleDefinition(**data)  # type: ignore[arg-type]


def _irrigate_rule(**overrides: object) -> RuleDefinition:
    data: dict = {
        "name": "irrigate_on_dry",
        "version": 1,
        "enabled": True,
        "priority": 20,
        "metric": SensorType.SUBSTRATE_MOISTURE,
        "comparator": RuleComparator.LT,
        "start_threshold": 35.0,
        "stop_threshold": 50.0,
        "target_actuator_type": ActuatorType.IRRIGATION_PUMP,
        "target_mode": ActuatorMode.ON,
        "target_output_ratio": 1.0,
        "cooldown_seconds": 60.0,
        "min_on_seconds": 60.0,
    }
    data.update(overrides)
    return RuleDefinition(**data)  # type: ignore[arg-type]


def test_temperature_closed_loop_cool_then_stop() -> None:
    """
    외기 고온 → 실내 상승 → HVAC START → (외기 완화 + 냉방) 온도 하락 → STOP.
    """
    params = EnvironmentModelParams(
        temp_outdoor_leak_per_s=1.0 / 900.0,
        temp_hvac_cool_per_s=0.03,
        temp_led_heat_per_s=0.0,
        temp_vent_mix_per_s=0.0,
    )
    initial = InitialEnvironmentState(temperature_c=27.5).to_environment_state()
    runner = ClosedLoopRunner(
        rule_set=RuleSet(
            rules=(
                _cool_rule(
                    start_threshold=28.0,
                    stop_threshold=26.0,
                    min_on_seconds=60.0,
                    cooldown_seconds=60.0,
                    target_output_ratio=1.0,
                ),
            )
        ),
        state=initial,
        outdoor=_outdoor_hot(),
        params=params,
        runtime=ControlRuntime(mode=ControlMode.AUTO),
    )

    # 1단계: 가열해 START 유도
    runner.run(steps=40, dt_seconds=30.0)
    assert any(
        app.event.event_type is ControlEventType.APPLIED
        for record in runner.history
        for app in record.applications
        if app.command.actuator_type is ActuatorType.HVAC
    ), "expected HVAC START"

    # 2단계: 외기를 낮춰 냉방 + 누설이 stop 임계 아래로 갈 수 있게
    runner.outdoor = OutdoorCondition(
        temperature_c=20.0,
        humidity_pct=40.0,
        simulation_time=runner.state.simulation_time,
        source="SYNTHETIC",
        co2_ppm=420.0,
    )
    runner.run(steps=80, dt_seconds=30.0)

    stop_events = [
        app
        for record in runner.history
        for app in record.applications
        if app.event.event_type is ControlEventType.STOPPED
        and app.command.actuator_type is ActuatorType.HVAC
    ]
    assert stop_events, "expected HVAC STOP after cooling"

    first_start = next(
        app
        for record in runner.history
        for app in record.applications
        if app.event.event_type is ControlEventType.APPLIED
        and app.command.actuator_type is ActuatorType.HVAC
    )
    temp_at_start = next(
        r.temperature_c
        for r in runner.history
        if r.simulation_time >= first_start.command.simulation_time
    )
    temps_after = [
        r.temperature_c
        for r in runner.history
        if r.simulation_time > first_start.command.simulation_time
    ]
    assert any(t < temp_at_start for t in temps_after)


def test_substrate_moisture_closed_loop_irrigate_then_stop() -> None:
    """관수 없음으로 건조 → 관수 START → 수분 상승 → STOP."""
    params = EnvironmentModelParams(
        substrate_drydown_per_s=0.001,
        substrate_irrigation_per_s=0.05,
        substrate_transpiration_per_s=0.0,
    )
    state = EnvironmentState(
        temperature_c=24.0,
        humidity_pct=60.0,
        co2_ppm=800.0,
        substrate_moisture_pct=32.0,  # start_threshold 35 아래
        ppfd_umol=0.0,
        simulation_time=0.0,
    )
    outdoor = OutdoorCondition(
        temperature_c=24.0,
        humidity_pct=60.0,
        simulation_time=0.0,
        source="SYNTHETIC",
    )
    runner = ClosedLoopRunner(
        rule_set=RuleSet(rules=(_irrigate_rule(min_on_seconds=30.0),)),
        state=state,
        outdoor=outdoor,
        params=params,
    )
    records = runner.run(steps=80, dt_seconds=30.0)

    applied = [
        app
        for record in records
        for app in record.applications
        if app.command.actuator_type is ActuatorType.IRRIGATION_PUMP
        and app.event.event_type is ControlEventType.APPLIED
    ]
    stopped = [
        app
        for record in records
        for app in record.applications
        if app.command.actuator_type is ActuatorType.IRRIGATION_PUMP
        and app.event.event_type is ControlEventType.STOPPED
    ]
    assert applied
    assert stopped
    assert max(r.substrate_moisture_pct for r in records) > 32.0


def test_no_duplicate_start_commands_while_running() -> None:
    """HVAC ON 유지 구간에서 START 명령이 매 스텝 나가지 않는다."""
    params = EnvironmentModelParams(
        temp_outdoor_leak_per_s=1.0 / 900.0,
        temp_hvac_cool_per_s=0.005,
    )
    runner = ClosedLoopRunner(
        rule_set=RuleSet(
            rules=(_cool_rule(min_on_seconds=300.0, cooldown_seconds=300.0),)
        ),
        state=InitialEnvironmentState(temperature_c=29.0).to_environment_state(),
        outdoor=_outdoor_hot(),
        params=params,
    )
    records = runner.run(steps=40, dt_seconds=30.0)
    starts = [
        app
        for record in records
        for app in record.applications
        if app.event.event_type is ControlEventType.APPLIED
        and app.command.actuator_type is ActuatorType.HVAC
    ]
    assert len(starts) == 1


def test_priority_conflict_only_higher_rule_commands() -> None:
    """동일 HVAC 를 겨냥한 두 규칙 → priority 낮은 숫자만 명령."""
    urgent = _cool_rule(name="urgent", priority=5, start_threshold=27.0)
    normal = _cool_rule(name="normal", priority=50, start_threshold=27.0)
    from app.domain.control.evaluate import MetricReading
    from app.domain.enums import ReadingQuality

    decisions = evaluate_ruleset(
        RuleSet(rules=(normal, urgent)),
        readings={
            SensorType.TEMPERATURE: MetricReading(
                SensorType.TEMPERATURE, 29.0, ReadingQuality.GOOD
            )
        },
    )
    assert len(decisions) == 1
    assert decisions[0].rule_name == "urgent"
    assert decisions[0].intent is RuleIntent.START


def test_chattering_suppressed_near_threshold_with_gates() -> None:
    """
    start/stop 사이 밴드에서 min_on 이 있으면
    짧은 시간에 START/STOP 이 번갈아 대량 발생하지 않는다.
    """
    params = EnvironmentModelParams(
        temp_outdoor_leak_per_s=1.0 / 1200.0,
        temp_hvac_cool_per_s=0.008,
    )
    runner = ClosedLoopRunner(
        rule_set=RuleSet(
            rules=(
                _cool_rule(
                    start_threshold=28.0,
                    stop_threshold=27.5,  # 좁은 밴드
                    min_on_seconds=180.0,
                    cooldown_seconds=180.0,
                ),
            )
        ),
        state=InitialEnvironmentState(temperature_c=28.2).to_environment_state(),
        outdoor=_outdoor_hot(),
        params=params,
    )
    records = runner.run(steps=60, dt_seconds=15.0)
    transitions = sum(len(record.applications) for record in records)
    # 게이트 없으면 수십 회 가능 — 여기선 소수여야 함
    assert transitions <= 4
