"""
Simulation run 라우터 (3단계 Day 11).

=============================================================================
경로 규칙
-----------------------------------------------------------------------------
브라우저 → Nginx `/api/...` → (prefix strip) → 이 라우터

예)
  POST /api/simulations/{id}/start  →  POST /simulations/{id}/start
  POST /api/simulations/{id}/step   →  POST /simulations/{id}/step

=============================================================================
계층
-----------------------------------------------------------------------------
이 파일은 HTTP 만 담당한다.
상태 전이·step 폐쇄 루프는 services.simulation 에 위임.
잘못된 상태 전이는 서비스가 409 를 올린다.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.simulation import (
    SimulationRunOut,
    SimulationStepRequest,
    SimulationStepResult,
)
from app.services import simulation as simulation_service

router = APIRouter(tags=["simulations"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/simulations", response_model=list[SimulationRunOut])
async def list_simulations(session: DbSession) -> list[SimulationRunOut]:
    """등록된 시뮬레이션 run 목록 (최신순)."""
    return await simulation_service.list_runs(session)


@router.get("/simulations/{run_id}", response_model=SimulationRunOut)
async def get_simulation(run_id: uuid.UUID, session: DbSession) -> SimulationRunOut:
    """단건 조회. 없으면 404."""
    return await simulation_service.get_run(session, run_id)


@router.post("/simulations/{run_id}/start", response_model=SimulationRunOut)
async def start_simulation(run_id: uuid.UUID, session: DbSession) -> SimulationRunOut:
    """
    CREATED / PAUSED / STOPPED → RUNNING.

    step 호출 전에 반드시 start 해야 한다.
    """
    return await simulation_service.start_run(session, run_id)


@router.post("/simulations/{run_id}/pause", response_model=SimulationRunOut)
async def pause_simulation(run_id: uuid.UUID, session: DbSession) -> SimulationRunOut:
    """RUNNING → PAUSED. 이후 step 은 409."""
    return await simulation_service.pause_run(session, run_id)


@router.post("/simulations/{run_id}/resume", response_model=SimulationRunOut)
async def resume_simulation(run_id: uuid.UUID, session: DbSession) -> SimulationRunOut:
    """PAUSED → RUNNING. 마지막 committed 시각·FarmState 부터 재개."""
    return await simulation_service.resume_run(session, run_id)


@router.post("/simulations/{run_id}/stop", response_model=SimulationRunOut)
async def stop_simulation(run_id: uuid.UUID, session: DbSession) -> SimulationRunOut:
    """RUNNING / PAUSED → STOPPED. ended_at 기록."""
    return await simulation_service.stop_run(session, run_id)


@router.post("/simulations/{run_id}/step", response_model=SimulationStepResult)
async def step_simulation(
    run_id: uuid.UUID,
    session: DbSession,
    body: SimulationStepRequest | None = None,
) -> SimulationStepResult:
    """
    RUNNING 상태에서 N 스텝 환경 전이 + (옵션) readings batch.

    body 생략 시 기본값: steps=1, dt_seconds=60, persist_readings=true.
    worker(runner.py) 가 같은 서비스를 직접 호출하므로, 이 엔드포인트는
    수동 진행·통합 테스트·임시 진입점 역할이다.
    """
    request = body or SimulationStepRequest()
    return await simulation_service.step_run(
        session,
        run_id,
        steps=request.steps,
        dt_seconds=request.dt_seconds,
        persist_readings=request.persist_readings,
    )
