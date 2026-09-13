"""
3단계 Day 9 — 실내 온·습도·CO₂ 상태전이 테스트.

검증 의도 (공식 방향성)
-----------------------
- 동일 입력 → 동일 출력 (결정성/재현성)
- 외기 ↑ → 실내 T ↑ (leak 항)
- HVAC ON → T ↓ (냉방 강제항)
- LED ON → T ↑, CO₂ ↓ (발열·광합성 흡수)
- 제습 ON → RH ↓
- 환기 ON + 고농도 CO₂ → 외기 쪽으로 CO₂ ↓
- Day 10 필드(배지·PPFD)는 Day 9 스텝에서 불변
"""

from app.domain.enums import ActuatorMode, ActuatorType
from app.domain.simulation.environment import (
    step_co2,
    step_environment,
    step_humidity,
    step_temperature,
)
from app.domain.simulation.state import (
    ActuatorCommandState,
    ActuatorInputs,
    EnvironmentState,
    InitialEnvironmentState,
    OutdoorCondition,
)


def _base_state(**overrides: float) -> EnvironmentState:
    initial = InitialEnvironmentState()
    state = initial.to_environment_state(simulation_time=0.0)
    if not overrides:
        return state
    data = {
        "temperature_c": state.temperature_c,
        "humidity_pct": state.humidity_pct,
        "co2_ppm": state.co2_ppm,
        "substrate_moisture_pct": state.substrate_moisture_pct,
        "ppfd_umol": state.ppfd_umol,
        "simulation_time": state.simulation_time,
    }
    data.update(overrides)
    return EnvironmentState(**data)


def _outdoor(*, temperature_c: float = 22.0, humidity_pct: float = 55.0) -> OutdoorCondition:
    return OutdoorCondition(
        temperature_c=temperature_c,
        humidity_pct=humidity_pct,
        simulation_time=0.0,
        source="SYNTHETIC",
        co2_ppm=420.0,
    )


def test_same_inputs_yield_same_temperature() -> None:
    first = step_temperature(
        24.0,
        outdoor_temperature_c=30.0,
        actuators=ActuatorInputs(),
        dt_seconds=60.0,
    )
    second = step_temperature(
        24.0,
        outdoor_temperature_c=30.0,
        actuators=ActuatorInputs(),
        dt_seconds=60.0,
    )
    assert first == second


def test_outdoor_heat_raises_indoor_temperature() -> None:
    """외기 상승 시 실내 온도가 올라간다 (설비 OFF)."""
    cooler = step_temperature(
        24.0,
        outdoor_temperature_c=20.0,
        actuators=ActuatorInputs(),
        dt_seconds=600.0,
    )
    warmer = step_temperature(
        24.0,
        outdoor_temperature_c=35.0,
        actuators=ActuatorInputs(),
        dt_seconds=600.0,
    )
    assert warmer > cooler
    assert warmer > 24.0


def test_hvac_cooling_lowers_temperature() -> None:
    off = step_temperature(
        28.0,
        outdoor_temperature_c=28.0,
        actuators=ActuatorInputs(),
        dt_seconds=300.0,
    )
    on = step_temperature(
        28.0,
        outdoor_temperature_c=28.0,
        actuators=ActuatorInputs(hvac=1.0),
        dt_seconds=300.0,
    )
    assert on < off
    assert on < 28.0


def test_led_adds_heat() -> None:
    dark = step_temperature(
        24.0,
        outdoor_temperature_c=24.0,
        actuators=ActuatorInputs(),
        dt_seconds=600.0,
    )
    lit = step_temperature(
        24.0,
        outdoor_temperature_c=24.0,
        actuators=ActuatorInputs(led=1.0),
        dt_seconds=600.0,
    )
    assert lit > dark


def test_dehumidifier_lowers_humidity() -> None:
    off = step_humidity(
        70.0,
        outdoor_humidity_pct=70.0,
        actuators=ActuatorInputs(),
        dt_seconds=300.0,
    )
    on = step_humidity(
        70.0,
        outdoor_humidity_pct=70.0,
        actuators=ActuatorInputs(dehumidifier=1.0),
        dt_seconds=300.0,
    )
    assert on < off


def test_ventilation_moves_co2_toward_outdoor() -> None:
    sealed = step_co2(
        1200.0,
        outdoor_co2_ppm=420.0,
        actuators=ActuatorInputs(),
        dt_seconds=900.0,
    )
    vented = step_co2(
        1200.0,
        outdoor_co2_ppm=420.0,
        actuators=ActuatorInputs(ventilation_fan=1.0),
        dt_seconds=900.0,
    )
    assert vented < sealed
    assert vented < 1200.0


def test_led_uptake_reduces_co2() -> None:
    dark = step_co2(
        900.0,
        outdoor_co2_ppm=900.0,
        actuators=ActuatorInputs(),
        dt_seconds=600.0,
    )
    lit = step_co2(
        900.0,
        outdoor_co2_ppm=900.0,
        actuators=ActuatorInputs(led=1.0),
        dt_seconds=600.0,
    )
    assert lit < dark


def test_step_environment_keeps_day10_fields() -> None:
    state = _base_state(substrate_moisture_pct=40.0, ppfd_umol=100.0)
    next_state = step_environment(
        state,
        outdoor=_outdoor(temperature_c=30.0),
        actuators=ActuatorInputs(hvac=0.5),
        dt_seconds=60.0,
    )
    assert next_state.substrate_moisture_pct == 40.0
    assert next_state.ppfd_umol == 100.0
    assert next_state.simulation_time == 60.0


def test_multi_step_trajectory_is_reproducible() -> None:
    def run() -> list[float]:
        state = _base_state()
        outdoor = _outdoor(temperature_c=32.0, humidity_pct=40.0)
        actuators = ActuatorInputs(hvac=0.3, ventilation_fan=0.2)
        temps: list[float] = []
        for _ in range(20):
            state = step_environment(
                state,
                outdoor=outdoor,
                actuators=actuators,
                dt_seconds=30.0,
            )
            temps.append(state.temperature_c)
        return temps

    assert run() == run()


def test_actuator_inputs_from_commands_uses_effective_ratio() -> None:
    inputs = ActuatorInputs.from_commands(
        [
            ActuatorCommandState(
                actuator_type=ActuatorType.HVAC,
                mode=ActuatorMode.OFF,
                output_ratio=1.0,
            ),
            ActuatorCommandState(
                actuator_type=ActuatorType.LED,
                mode=ActuatorMode.ON,
                output_ratio=0.7,
            ),
        ]
    )
    assert inputs.hvac == 0.0
    assert inputs.led == 0.7
