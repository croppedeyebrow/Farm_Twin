"""
Simulation run 라우터 (3단계 Day 11).

경로 (Nginx `/api` strip 후)
-----------------------------
GET  /simulations
GET  /simulations/{id}
POST /simulations/{id}/start|pause|resume|stop
POST /simulations/{id}/step
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
    """시뮬레이션 run 목록."""
    return await simulation_service.list_runs(session)


@router.get("/simulations/{run_id}", response_model=SimulationRunOut)
async def get_simulation(run_id: uuid.UUID, session: DbSession) -> SimulationRunOut:
    """단건 조회."""
    return await simulation_service.get_run(session, run_id)


@router.post("/simulations/{run_id}/start", response_model=SimulationRunOut)
async def start_simulation(run_id: uuid.UUID, session: DbSession) -> SimulationRunOut:
    """CREATED/PAUSED/STOPPED → RUNNING."""
    return await simulation_service.start_run(session, run_id)


@router.post("/simulations/{run_id}/pause", response_model=SimulationRunOut)
async def pause_simulation(run_id: uuid.UUID, session: DbSession) -> SimulationRunOut:
    """RUNNING → PAUSED."""
    return await simulation_service.pause_run(session, run_id)


@router.post("/simulations/{run_id}/resume", response_model=SimulationRunOut)
async def resume_simulation(run_id: uuid.UUID, session: DbSession) -> SimulationRunOut:
    """PAUSED → RUNNING."""
    return await simulation_service.resume_run(session, run_id)


@router.post("/simulations/{run_id}/stop", response_model=SimulationRunOut)
async def stop_simulation(run_id: uuid.UUID, session: DbSession) -> SimulationRunOut:
    """RUNNING/PAUSED → STOPPED."""
    return await simulation_service.stop_run(session, run_id)


@router.post("/simulations/{run_id}/step", response_model=SimulationStepResult)
async def step_simulation(
    run_id: uuid.UUID,
    session: DbSession,
    body: SimulationStepRequest | None = None,
) -> SimulationStepResult:
    """
    RUNNING 상태에서 N 스텝 환경 전이 + (옵션) readings batch.

    worker 루프가 붙기 전 API/테스트용 진입점.
    """
    request = body or SimulationStepRequest()
    return await simulation_service.step_run(
        session,
        run_id,
        steps=request.steps,
        dt_seconds=request.dt_seconds,
        persist_readings=request.persist_readings,
    )
