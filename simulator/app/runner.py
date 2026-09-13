"""
Simulator worker 1차 (3단계 Day 11).

=============================================================================
역할
-----------------------------------------------------------------------------
별도 프로세스/컨테이너에서 돌리는 시뮬레이터 진입점.
FastAPI 를 거치지 않고 **같은** services.simulation 계약을 직접 호출한다.
(백엔드 설계: API 와 simulator 책임 분리, 계산/저장 계약은 공유)

흐름
----
  1. start_run
  2. step_run 을 batch_size 단위로 반복 (commit 경계를 나눔)
  3. stop_run
  4. engine.dispose

기본 예 (1시간 가상 시계열)
----------------------------
    cd backend && uv run python ../simulator/app/runner.py --steps 60 --dt-seconds 60

run id 기본값 = seed MVP 고정 UUID (44444444-...).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

# monorepo: backend 패키지를 import 할 수 있게 path 추가
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
    """
    start → step 루프 → stop.

    batch_size: 한 트랜잭션(step_run 한 호출)에 묶을 스텝 수.
    너무 크면 장시간 락, 너무 작으면 커밋 오버헤드.
    노이즈는 (seed, type, simulation_time) 으로 결정적이라 배치 분할 재현성에 안전.
    """
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
            # 로그의 T/PPFD 는 참값 (FarmState)
            print(
                f"t={result.simulation_time_seconds:.0f}s "
                f"T={result.temperature_c:.2f} PPFD={result.ppfd_umol:.0f} "
                f"readings+={result.readings_inserted} version={result.farm_state_version}"
            )
        remaining -= chunk

    async with SessionLocal() as session:
        stopped = await simulation_service.stop_run(session, run_id)
        print(f"stopped status={stopped.status} ended_at={stopped.ended_at}")

    # Windows/프로세스 종료 시 풀 정리
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="FarmTwin simulator worker (Day 11)")
    parser.add_argument("--run-id", default=str(RUN_ID), help="SimulationRun UUID")
    parser.add_argument("--steps", type=int, default=60, help="총 가상 스텝 수")
    parser.add_argument(
        "--dt-seconds",
        type=float,
        default=60.0,
        help="스텝당 가상 초 (60×60=1시간)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="한 번 step_run 호출에 묶을 스텝 수",
    )
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
