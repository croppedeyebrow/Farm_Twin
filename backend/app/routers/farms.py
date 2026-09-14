"""
Farm CRUD / snapshot 라우터 (2단계 Day 7).

경로 규칙
---------
브라우저 → Nginx `/api/...` → (prefix strip) → 이 라우터의 `/farms...`

예) GET /api/farms/{id}/snapshot  →  GET /farms/{id}/snapshot

DbSession
---------
`Annotated[..., Depends(get_db)]` 로 FastAPI 의존성 주입.
요청마다 AsyncSession 이 열리고, 종료 시 컨텍스트가 닫힌다.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.farm import (
    ActuatorSummary,
    ControlEventOut,
    FarmSnapshot,
    FarmStateOut,
    FarmSummary,
    SensorReadingOut,
    SensorSummary,
)
from app.services import farm as farm_service

router = APIRouter(tags=["farms"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/farms", response_model=list[FarmSummary])
async def list_farms(session: DbSession) -> list[FarmSummary]:
    """농장 목록."""
    return await farm_service.list_farms(session)


@router.get("/farms/{farm_id}", response_model=FarmSummary)
async def get_farm(farm_id: uuid.UUID, session: DbSession) -> FarmSummary:
    """농장 단건."""
    farm = await farm_service.get_farm_or_404(session, farm_id)
    return FarmSummary.model_validate(farm)


@router.get("/farms/{farm_id}/snapshot", response_model=FarmSnapshot)
async def get_farm_snapshot(farm_id: uuid.UUID, session: DbSession) -> FarmSnapshot:
    """관제 초기 로딩용 통합 스냅샷 (메타 + 참값)."""
    return await farm_service.get_farm_snapshot(session, farm_id)


@router.get("/farms/{farm_id}/state", response_model=FarmStateOut)
async def get_farm_state(farm_id: uuid.UUID, session: DbSession) -> FarmStateOut:
    """환경 참값만 조회."""
    return await farm_service.get_farm_state(session, farm_id)


@router.get("/farms/{farm_id}/sensors", response_model=list[SensorSummary])
async def list_farm_sensors(
    farm_id: uuid.UUID,
    session: DbSession,
) -> list[SensorSummary]:
    """농장 센서 메타데이터 목록."""
    return await farm_service.list_farm_sensors(session, farm_id)


@router.get("/farms/{farm_id}/actuators", response_model=list[ActuatorSummary])
async def list_farm_actuators(
    farm_id: uuid.UUID,
    session: DbSession,
) -> list[ActuatorSummary]:
    """농장 액추에이터 목록."""
    return await farm_service.list_farm_actuators(session, farm_id)


@router.get("/farms/{farm_id}/events", response_model=list[ControlEventOut])
async def list_farm_events(
    farm_id: uuid.UUID,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ControlEventOut]:
    """
    제어 이벤트 타임라인 (5단계 Day 18).

    최신 recorded_at 순. 관제 UI EventTimeline 이 REST 로 이력을 채운다.
    """
    return await farm_service.list_farm_control_events(session, farm_id, limit=limit)


@router.get("/sensors/{sensor_id}/readings", response_model=list[SensorReadingOut])
async def list_sensor_readings(
    sensor_id: uuid.UUID,
    session: DbSession,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[SensorReadingOut]:
    """센서 측정 이력 (simulation_time 내림차순)."""
    return await farm_service.list_sensor_readings(session, sensor_id, limit=limit)
