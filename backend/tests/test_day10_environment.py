"""
3단계 Day 10 — 배지수분·PPFD·설정 파일·clamp 테스트.

검증 의도
---------
- 관수 없음 → 배지수분 감소
- 관수 ON → 배지수분 증가
- LED ON → PPFD 상승 + (연동) CO₂ 흡수
- TOML 로드·재현성·clamp
"""

from pathlib import Path

import pytest

from app.domain.simulation.config_loader import (
    DEFAULT_CONFIG_PATH,
    load_environment_params,
)
from app.domain.simulation.environment import (
    step_environment,
    step_ppfd,
    step_substrate_moisture,
)
from app.domain.simulation.params import DEFAULT_ENV_PARAMS, EnvironmentModelParams
from app.domain.simulation.state import (
    ActuatorInputs,
    EnvironmentState,
    InitialEnvironmentState,
    OutdoorCondition,
)


def _outdoor() -> OutdoorCondition:
    return OutdoorCondition(
        temperature_c=24.0,
        humidity_pct=60.0,
        simulation_time=0.0,
        source="SYNTHETIC",
    )


def test_substrate_drydown_without_irrigation() -> None:
    """관수 없음 시 배지수분이 감소한다."""
    next_m = step_substrate_moisture(
        50.0,
        actuators=ActuatorInputs(),
        dt_seconds=3600.0,
    )
    assert next_m < 50.0


def test_irrigation_increases_substrate_moisture() -> None:
    dry = step_substrate_moisture(
        40.0,
        actuators=ActuatorInputs(),
        dt_seconds=600.0,
    )
    wet = step_substrate_moisture(
        40.0,
        actuators=ActuatorInputs(irrigation_pump=1.0),
        dt_seconds=600.0,
    )
    assert wet > dry
    assert wet > 40.0


def test_led_increases_ppfd() -> None:
    dark = step_ppfd(0.0, actuators=ActuatorInputs(), dt_seconds=60.0)
    lit = step_ppfd(0.0, actuators=ActuatorInputs(led=1.0), dt_seconds=60.0)
    assert lit > dark
    assert lit > 0.0


def test_ppfd_tracks_led_output_ratio() -> None:
    """풀출력에 수렴하는 PPFD."""
    params = EnvironmentModelParams(ppfd_track_per_s=1.0)
    steady = step_ppfd(
        0.0,
        actuators=ActuatorInputs(led=1.0),
        dt_seconds=10.0,
        params=params,
    )
    assert steady == pytest.approx(params.ppfd_led_max_umol, rel=1e-6)


def test_led_on_raises_ppfd_and_heat_in_full_step() -> None:
    state = InitialEnvironmentState().to_environment_state()
    outdoor = _outdoor()
    dark = step_environment(
        state,
        outdoor=outdoor,
        actuators=ActuatorInputs(),
        dt_seconds=300.0,
    )
    lit = step_environment(
        state,
        outdoor=outdoor,
        actuators=ActuatorInputs(led=1.0),
        dt_seconds=300.0,
    )
    assert lit.ppfd_umol > dark.ppfd_umol
    assert lit.temperature_c > dark.temperature_c


def test_substrate_clamped_at_zero() -> None:
    params = EnvironmentModelParams(substrate_drydown_per_s=1.0)
    value = step_substrate_moisture(
        5.0,
        actuators=ActuatorInputs(),
        dt_seconds=100.0,
        params=params,
    )
    assert value == params.substrate_moisture_min_pct


def test_load_default_config_file() -> None:
    assert DEFAULT_CONFIG_PATH.is_file()
    loaded = load_environment_params()
    assert loaded.ppfd_led_max_umol == pytest.approx(800.0)
    assert loaded.substrate_drydown_per_s == pytest.approx(0.00008)


def test_load_config_from_custom_toml(tmp_path: Path) -> None:
    path = tmp_path / "custom.toml"
    path.write_text(
        """
[environment_model]
ppfd_led_max_umol = 1200.0
substrate_drydown_per_s = 0.0001
unknown_key = 999
""".strip(),
        encoding="utf-8",
    )
    loaded = load_environment_params(path)
    assert loaded.ppfd_led_max_umol == 1200.0
    assert loaded.substrate_drydown_per_s == 0.0001
    assert loaded.temp_hvac_cool_per_s == DEFAULT_ENV_PARAMS.temp_hvac_cool_per_s


def test_missing_config_returns_defaults() -> None:
    loaded = load_environment_params(Path("/nonexistent/environment_model.toml"))
    assert loaded == DEFAULT_ENV_PARAMS


def test_day10_trajectory_reproducible() -> None:
    def run() -> EnvironmentState:
        state = InitialEnvironmentState().to_environment_state()
        params = load_environment_params()
        for _ in range(30):
            state = step_environment(
                state,
                outdoor=_outdoor(),
                actuators=ActuatorInputs(led=0.5, irrigation_pump=0.1),
                dt_seconds=60.0,
                params=params,
            )
        return state

    a = run()
    b = run()
    assert a == b
