"""
3단계 Day 11 — 가상 센서·재현성·noise≠FarmState 단위 테스트.

DB 없이 도메인만 검증한다.
"""

from dataclasses import replace

from app.domain.enums import SensorType
from app.domain.simulation.sensors import (
    SensorChannelConfig,
    VirtualSensorBank,
    true_value_for,
)
from app.domain.simulation.state import (
    EnvironmentState,
    InitialEnvironmentState,
)


def _state(**overrides: float) -> EnvironmentState:
    base = InitialEnvironmentState().to_environment_state(simulation_time=100.0)
    data = {
        "temperature_c": base.temperature_c,
        "humidity_pct": base.humidity_pct,
        "co2_ppm": base.co2_ppm,
        "substrate_moisture_pct": base.substrate_moisture_pct,
        "ppfd_umol": base.ppfd_umol,
        "simulation_time": base.simulation_time,
    }
    data.update(overrides)
    return EnvironmentState(**data)


def test_same_seed_same_measurements() -> None:
    state = _state()
    channels = (
        SensorChannelConfig(SensorType.TEMPERATURE, offset=0.2, noise_std=0.1),
    )

    def run() -> list[float]:
        bank = VirtualSensorBank(seed=42, channels=channels)
        return [bank.measure(state)[0].value for _ in range(5)]

    assert run() == run()


def test_different_seed_different_noise() -> None:
    state = _state()
    channels = (
        SensorChannelConfig(SensorType.TEMPERATURE, offset=0.0, noise_std=1.0),
    )
    a = VirtualSensorBank(seed=1, channels=channels).measure(state)[0].value
    b = VirtualSensorBank(seed=2, channels=channels).measure(state)[0].value
    assert a != b


def test_measure_does_not_mutate_environment_state() -> None:
    """센서 noise 가 FarmState/참값을 바꾸지 않는다."""
    state = _state(temperature_c=24.0)
    before = (
        state.temperature_c,
        state.humidity_pct,
        state.co2_ppm,
        state.substrate_moisture_pct,
        state.ppfd_umol,
        state.simulation_time,
    )
    bank = VirtualSensorBank(seed=7)
    samples = bank.measure(state)
    after = (
        state.temperature_c,
        state.humidity_pct,
        state.co2_ppm,
        state.substrate_moisture_pct,
        state.ppfd_umol,
        state.simulation_time,
    )
    assert before == after
    assert len(samples) == 5
    # 기본 채널은 offset/noise 가 있어 측정 ≠ 참값인 경우가 일반적
    temp = next(s for s in samples if s.sensor_type is SensorType.TEMPERATURE)
    assert temp.true_value == true_value_for(state, SensorType.TEMPERATURE)
    assert temp.value != temp.true_value


def test_offset_applied_without_noise() -> None:
    state = _state(temperature_c=20.0)
    channels = (
        SensorChannelConfig(SensorType.TEMPERATURE, offset=1.5, noise_std=0.0),
    )
    sample = VirtualSensorBank(seed=0, channels=channels).measure(state)[0]
    assert sample.value == 21.5
    assert sample.true_value == 20.0


def test_delay_uses_past_true_value() -> None:
    channels = (
        SensorChannelConfig(
            SensorType.TEMPERATURE,
            offset=0.0,
            noise_std=0.0,
            delay_steps=2,
        ),
    )
    bank = VirtualSensorBank(seed=0, channels=channels)
    s0 = bank.measure(_state(temperature_c=10.0, simulation_time=0.0))[0]
    s1 = bank.measure(_state(temperature_c=20.0, simulation_time=1.0))[0]
    s2 = bank.measure(_state(temperature_c=30.0, simulation_time=2.0))[0]
    # delay=2: 세 번째 측정에서 첫 참값(10)이 나와야 함
    assert s0.value == 10.0
    assert s1.value == 10.0
    assert s2.value == 10.0


def test_frozen_state_replace_is_independent() -> None:
    state = _state()
    other = replace(state, temperature_c=99.0)
    assert state.temperature_c != other.temperature_c
