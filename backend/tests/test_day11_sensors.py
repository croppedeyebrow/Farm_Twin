"""
3단계 Day 11 — 가상 센서·재현성·noise≠FarmState 단위 테스트.

DB 없이 도메인만 검증한다.

검증 의도
---------
- 동일 seed → 동일 측정 시계열 (결정성)
- 다른 seed → 다른 노이즈
- measure() 가 EnvironmentState 를 변경하지 않음 (3단계 완료 기준)
- offset 만 있을 때 y = true + offset
- delay_steps=N 이면 N 스텝 전 참값이 관측됨
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
    """테스트용 참값 스냅샷. overrides 로 개별 필드만 덮어쓴다."""
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
    """동일 seed·동일 참값 → 측정값 시계열 비트 동일."""
    state = _state()
    channels = (
        SensorChannelConfig(SensorType.TEMPERATURE, offset=0.2, noise_std=0.1),
    )

    def run() -> list[float]:
        bank = VirtualSensorBank(seed=42, channels=channels)
        return [bank.measure(state)[0].value for _ in range(5)]

    assert run() == run()


def test_different_seed_different_noise() -> None:
    """seed 가 바뀌면 노이즈 항이 달라진다."""
    state = _state()
    channels = (
        SensorChannelConfig(SensorType.TEMPERATURE, offset=0.0, noise_std=1.0),
    )
    a = VirtualSensorBank(seed=1, channels=channels).measure(state)[0].value
    b = VirtualSensorBank(seed=2, channels=channels).measure(state)[0].value
    assert a != b


def test_measure_does_not_mutate_environment_state() -> None:
    """센서 noise 가 참값(EnvironmentState)을 바꾸지 않는다."""
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
    # 기본 채널은 offset/noise 가 있어 측정 ≠ 참값
    temp = next(s for s in samples if s.sensor_type is SensorType.TEMPERATURE)
    assert temp.true_value == true_value_for(state, SensorType.TEMPERATURE)
    assert temp.value != temp.true_value


def test_offset_applied_without_noise() -> None:
    """σ=0 이면 y = true + offset 정확히."""
    state = _state(temperature_c=20.0)
    channels = (
        SensorChannelConfig(SensorType.TEMPERATURE, offset=1.5, noise_std=0.0),
    )
    sample = VirtualSensorBank(seed=0, channels=channels).measure(state)[0]
    assert sample.value == 21.5
    assert sample.true_value == 20.0


def test_delay_uses_past_true_value() -> None:
    """
    delay_steps=2 이면 버퍼가 찬 뒤 2스텝 전 참값을 낸다.

    t0: true=10 → 관측 10 (워밍업)
    t1: true=20 → 관측 10
    t2: true=30 → 관측 10  (인덱스 -1-2)
    """
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
    assert s0.value == 10.0
    assert s1.value == 10.0
    assert s2.value == 10.0


def test_frozen_state_replace_is_independent() -> None:
    """EnvironmentState 는 frozen — replace 가 원본을 건드리지 않는다."""
    state = _state()
    other = replace(state, temperature_c=99.0)
    assert state.temperature_c != other.temperature_c
