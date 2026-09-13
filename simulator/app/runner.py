"""
Simulator worker 1차 (3단계 Day 11).

API 서비스의 step_run 을 반복 호출하는 단순 루프.
별도 컨테이너에서 돌릴 때:

    cd backend && uv run python ../simulator/app/runner.py --steps 60

기본 run id 는 seed MVP 고정 UUID.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.db.seed import RUN_ID  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.services import simulation as simulation_service  # noqa: E402


async def run_worker(
    *,
    run_id: uuid.UUID,
    steps: int,
    dt_seconds: float,
    batch_size: int,
) -> None:
    async with SessionLocal() as session:
        started = await simulation_service.start_run(session, run_id)
        print(f"started status={started.status} t={started.simulation_time_seconds}")

    remaining = steps
    while remaining > 0:
        chunk = min(batch_size, remaining)
        async with SessionLocal() as session:
            result = await simulation_service.step_run(
                session,
                run_id,
                steps=chunk,
                dt_seconds=dt_seconds,
                persist_readings=True,
            )
            print(
                f"t={result.simulation_time_seconds:.0f}s "
                f"T={result.temperature_c:.2f} PPFD={result.ppfd_umol:.0f} "
                f"readings+={result.readings_inserted} version={result.farm_state_version}"
            )
        remaining -= chunk

    async with SessionLocal() as session:
        stopped = await simulation_service.stop_run(session, run_id)
        print(f"stopped status={stopped.status} ended_at={stopped.ended_at}")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="FarmTwin simulator worker (Day 11)")
    parser.add_argument("--run-id", default=str(RUN_ID))
    parser.add_argument("--steps", type=int, default=60, help="총 가상 스텝 수")
    parser.add_argument("--dt-seconds", type=float, default=60.0)
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(
        run_worker(
            run_id=uuid.UUID(args.run_id),
            steps=args.steps,
            dt_seconds=args.dt_seconds,
            batch_size=args.batch_size,
        )
    )


if __name__ == "__main__":
    main()
