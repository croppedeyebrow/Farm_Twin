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

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.fault import (
    FaultClearRequest,
    FaultInjectRequest,
    FaultListOut,
    FaultOut,
)
from app.schemas.history import QualityReportOut, ReadingHistoryOut
from app.schemas.lineage import EventLineageOut, RunLineageOut
from app.schemas.replay import (
    ReplayCompareOut,
    ReplayDataset,
    ReplayImportRequest,
    ReplayRunOut,
    ReplayRunRequest,
)
from app.schemas.simulation import (
    SimulationRunOut,
    SimulationStepRequest,
    SimulationStepResult,
)
from app.schemas.telemetry import TelemetryIngestRequest, TelemetryIngestResult
from app.services import faults as fault_service
from app.services import history as history_service
from app.services import lineage as lineage_service
from app.services import replay as replay_service
from app.services import simulation as simulation_service
from app.services import telemetry as telemetry_service

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


@router.post("/simulations/{run_id}/readings", response_model=TelemetryIngestResult)
async def ingest_readings(
    run_id: uuid.UUID,
    body: TelemetryIngestRequest,
    session: DbSession,
) -> TelemetryIngestResult:
    """
    외부 reading 배치 적재 (RUNNING / PAUSED).

    각 reading 은 센서별 sequence 필수. 중복·역순은 거부하고,
    건너뛴 sequence 는 quality=missing 마커로 남긴다.
    """
    return await telemetry_service.ingest_readings(session, run_id, body)


@router.post("/simulations/{run_id}/faults", response_model=FaultOut, status_code=201)
async def inject_fault(
    run_id: uuid.UUID,
    body: FaultInjectRequest,
    session: DbSession,
) -> FaultOut:
    """
    센서 고장 주입 (spike / stuck / dropout).

    시작 시각은 run 의 현재 가상 시각. 다음 step 측정부터 적용된다.
    센서당 진행 중 고장은 하나 — 겹치면 409.
    """
    return await fault_service.inject_fault(session, run_id, body)


@router.post("/simulations/{run_id}/faults/{fault_id}/clear", response_model=FaultOut)
async def clear_fault(
    run_id: uuid.UUID,
    fault_id: uuid.UUID,
    session: DbSession,
    body: FaultClearRequest | None = None,
) -> FaultOut:
    """고장 해제. end_simulation_time·cleared_at 을 기록하고 다음 step 부터 정상 측정."""
    return await fault_service.clear_fault(session, run_id, fault_id, body)


@router.get("/simulations/{run_id}/faults", response_model=FaultListOut)
async def list_faults(run_id: uuid.UUID, session: DbSession) -> FaultListOut:
    """run 의 고장 시작·해제 이력 (최신순)."""
    return await fault_service.list_run_faults(session, run_id)


# ---------------------------------------------------------------------------
# Day 23: replay · lineage · 이력 집계 · 품질 리포트
# ---------------------------------------------------------------------------


@router.get("/simulations/{run_id}/dataset", response_model=ReplayDataset)
async def export_replay_dataset(run_id: uuid.UUID, session: DbSession) -> ReplayDataset:
    """재생 데이터셋(farmtwin.replay.v1) export. 체크포인트 없는 run 은 409."""
    return await replay_service.export_dataset(session, run_id)


@router.post("/simulations/replay", response_model=SimulationRunOut, status_code=201)
async def import_replay_dataset(
    body: ReplayImportRequest,
    session: DbSession,
) -> SimulationRunOut:
    """데이터셋 import → 재생 run(CREATED). 룸·센서·설비가 없으면 422."""
    return await replay_service.import_dataset(session, body)


@router.post("/simulations/{run_id}/replay/run", response_model=ReplayRunOut)
async def run_replay(
    run_id: uuid.UUID,
    session: DbSession,
    body: ReplayRunRequest | None = None,
) -> ReplayRunOut:
    """
    재생 run 을 원본 스텝 간격대로 진행하고 비교 결과를 돌려준다.

    같은 룸의 RUNNING run 은 먼저 PAUSED 로 돌린다 (paused_run_ids).
    """
    request = body or ReplayRunRequest()
    return await replay_service.run_replay(session, run_id, max_steps=request.max_steps)


@router.get("/simulations/{run_id}/replay/compare", response_model=ReplayCompareOut)
async def compare_replay(run_id: uuid.UUID, session: DbSession) -> ReplayCompareOut:
    """재생 run 결과 ↔ 원본 기대 결과 비교."""
    return await replay_service.compare_replay(session, run_id)


@router.get("/simulations/{run_id}/lineage", response_model=RunLineageOut)
async def run_lineage(run_id: uuid.UUID, session: DbSession) -> RunLineageOut:
    """run 의 seed·모델·규칙 묶음·체크포인트·산출물 수·재생 관계."""
    return await lineage_service.get_run_lineage(session, run_id)


@router.get("/control-events/{event_id}/lineage", response_model=EventLineageOut)
async def event_lineage(event_id: uuid.UUID, session: DbSession) -> EventLineageOut:
    """이벤트 → 명령 → 규칙 개정 → 근거 reading → 외기 스냅샷 → run."""
    return await lineage_service.get_event_lineage(session, event_id)


@router.get("/simulations/{run_id}/readings/history", response_model=ReadingHistoryOut)
async def run_reading_history(
    run_id: uuid.UUID,
    session: DbSession,
    sensor_code: str | None = None,
    bucket_seconds: Annotated[int, Query()] = 60,
    start: float | None = None,
    end: float | None = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 240,
) -> ReadingHistoryOut:
    """측정 이력. bucket_seconds=0 원시, 60 = 1분, 300 = 5분 집계 (가상 시계 기준)."""
    return await history_service.run_reading_history(
        session,
        run_id,
        sensor_code=sensor_code,
        bucket_seconds=bucket_seconds,
        start=start,
        end=end,
        limit=limit,
    )


@router.get("/simulations/{run_id}/quality-report", response_model=QualityReportOut)
async def run_quality_report(run_id: uuid.UUID, session: DbSession) -> QualityReportOut:
    """run 전체 구간 센서별 품질 분포·주요 사유·고장 구간."""
    return await history_service.run_quality_report(session, run_id)
