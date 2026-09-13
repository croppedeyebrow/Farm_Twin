"""
Day 8~10 데모: 시계 + 외기 + 전 환경 상태전이.

backend 의 domain.simulation 을 import 한다.
계수는 simulator/config/environment_model.toml 을 로드한다.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.domain.simulation.clock import SimulationClock  # noqa: E402
from app.domain.simulation.config_loader import load_environment_params  # noqa: E402
from app.domain.simulation.environment import step_environment  # noqa: E402
from app.domain.simulation.state import (  # noqa: E402
    ActuatorInputs,
    InitialEnvironmentState,
)
from app.domain.simulation.weather import create_weather_adapter  # noqa: E402


async def run_demo(*, steps: int = 8, seed: int = 42) -> None:
    params = load_environment_params()
    clock = SimulationClock(
        seed=seed,
        step_seconds=1.0,
        speed_multiplier=60.0,
    )
    weather = create_weather_adapter("SYNTHETIC", seed=seed)
    state = InitialEnvironmentState().to_environment_state()
    actuators = ActuatorInputs(ventilation_fan=0.2, led=0.6)
    print(
        f"seed={seed} params.ppfd_max={params.ppfd_led_max_umol} "
        f"initial T={state.temperature_c} substrate={state.substrate_moisture_pct}%"
    )
    prev = clock.now_seconds
    for _ in range(steps):
        now = clock.advance()
        dt = now - prev
        prev = now
        outdoor = await weather.read(now)
        state = step_environment(
            state,
            outdoor=outdoor,
            actuators=actuators,
            dt_seconds=dt,
            params=params,
        )
        print(
            f"t={now:.0f}s T={state.temperature_c:.2f} RH={state.humidity_pct:.1f} "
            f"CO2={state.co2_ppm:.0f} substrate={state.substrate_moisture_pct:.2f}% "
            f"PPFD={state.ppfd_umol:.0f}"
        )


def main() -> None:
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
