"""
Day 8~9 데모: SimulationClock + SYNTHETIC 외기 + 온·습·CO₂ 상태전이.

backend 의 domain.simulation 을 import 한다.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# monorepo: backend/ 를 import path 에 추가
_BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.domain.simulation.clock import SimulationClock  # noqa: E402
from app.domain.simulation.environment import step_environment  # noqa: E402
from app.domain.simulation.state import (  # noqa: E402
    ActuatorInputs,
    InitialEnvironmentState,
)
from app.domain.simulation.weather import create_weather_adapter  # noqa: E402


async def run_demo(*, steps: int = 8, seed: int = 42) -> None:
    clock = SimulationClock(
        seed=seed,
        step_seconds=1.0,
        speed_multiplier=60.0,  # 1 step = 60 가상 초
    )
    weather = create_weather_adapter("SYNTHETIC", seed=seed)
    state = InitialEnvironmentState().to_environment_state()
    # 데모: 약한 환기만 (HVAC OFF) — 외기 영향이 보이게
    actuators = ActuatorInputs(ventilation_fan=0.2)
    print(f"seed={seed} initial T={state.temperature_c} H={state.humidity_pct} CO2={state.co2_ppm}")
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
        )
        print(
            f"t={now:.0f}s outT={outdoor.temperature_c:.1f} "
            f"inT={state.temperature_c:.2f} RH={state.humidity_pct:.1f} "
            f"CO2={state.co2_ppm:.0f}"
        )


def main() -> None:
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
