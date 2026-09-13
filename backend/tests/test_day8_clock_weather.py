"""3단계 Day 8 — SimulationClock / 외기 adapter / 초기 상태 테스트."""

import pytest

from app.domain.simulation.clock import SimulationClock
from app.domain.simulation.state import InitialEnvironmentState
from app.domain.simulation.weather import (
    ReplayWeatherAdapter,
    SyntheticWeatherAdapter,
    create_weather_adapter,
)


def test_clock_advances_with_step_and_speed() -> None:
    clock = SimulationClock(seed=42, step_seconds=1.0, speed_multiplier=60.0)
    assert clock.advance() == 60.0
    assert clock.advance() == 120.0
    assert clock.step_count == 2


def test_clock_pause_blocks_advance() -> None:
    clock = SimulationClock(seed=1, step_seconds=5.0, speed_multiplier=1.0)
    clock.advance()
    clock.pause()
    paused_at = clock.now_seconds
    assert clock.advance() == paused_at
    clock.resume()
    assert clock.advance() == paused_at + 5.0


def test_clock_rejects_invalid_step() -> None:
    with pytest.raises(ValueError):
        SimulationClock(seed=0, step_seconds=0)


@pytest.mark.asyncio
async def test_same_seed_synthetic_weather_is_reproducible() -> None:
    async def sample(seed: int) -> list[float]:
        adapter = SyntheticWeatherAdapter(seed=seed)
        return [(await adapter.read(t)).temperature_c for t in (0.0, 3600.0, 7200.0)]

    first = await sample(7)
    second = await sample(7)
    other = await sample(8)
    assert first == second
    assert first != other


@pytest.mark.asyncio
async def test_replay_weather_holds_last_sample() -> None:
    adapter = ReplayWeatherAdapter(
        [
            (0.0, 20.0, 50.0),
            (10.0, 21.0, 51.0),
            (20.0, 22.0, 52.0),
        ]
    )
    mid = await adapter.read(15.0)
    assert mid.temperature_c == 21.0
    assert mid.source == "REPLAY"


@pytest.mark.asyncio
async def test_create_weather_adapter_modes() -> None:
    synthetic = create_weather_adapter("SYNTHETIC", seed=1)
    assert synthetic.mode == "SYNTHETIC"
    api = create_weather_adapter("API", seed=1)
    assert api.mode == "API"
    outdoor = await api.read(0.0)
    assert outdoor.source == "API"


def test_initial_state_defaults_and_validation() -> None:
    state = InitialEnvironmentState()
    assert state.temperature_c == 24.0
    with pytest.raises(ValueError):
        InitialEnvironmentState(humidity_pct=120.0)


def test_clock_reset_keeps_seed() -> None:
    clock = SimulationClock(seed=99, step_seconds=1.0)
    clock.advance()
    clock.reset()
    assert clock.seed == 99
    assert clock.now_seconds == 0.0
    assert clock.step_count == 0
