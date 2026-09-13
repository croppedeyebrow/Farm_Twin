"""
Day 8 데모: SimulationClock + SYNTHETIC 외기 몇 스텝 출력.

backend 의 domain.simulation 을 import 한다.
상태전이(Day 9+) 이전의 계약 확인용.
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
from app.domain.simulation.state import InitialEnvironmentState  # noqa: E402
from app.domain.simulation.weather import create_weather_adapter  # noqa: E402


async def run_demo(*, steps: int = 5, seed: int = 42) -> None:
    clock = SimulationClock(
        seed=seed,
        step_seconds=1.0,
        speed_multiplier=60.0,  # 1 step = 60 가상 초
    )
    weather = create_weather_adapter("SYNTHETIC", seed=seed)
    indoor = InitialEnvironmentState()
    print(f"seed={seed} initial_indoor={indoor}")
    for _ in range(steps):
        now = clock.advance()
        outdoor = await weather.read(now)
        print(
            f"t={now:.0f}s outdoor_T={outdoor.temperature_c:.2f}C "
            f"RH={outdoor.humidity_pct:.1f}% source={outdoor.source}"
        )


def main() -> None:
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
