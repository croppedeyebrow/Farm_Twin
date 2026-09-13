"""Farm CRUD / snapshot 라우터 (2단계 Day 7).

Nginx `/api` strip 이후 경로: `/farms`, `/farms/{id}/state` …
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.farm import (
    ActuatorSummary,
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
    return await farm_service.list_farms(session)


@router.get("/farms/{farm_id}", response_model=FarmSummary)
async def get_farm(farm_id: uuid.UUID, session: DbSession) -> FarmSummary:
    farm = await farm_service.get_farm_or_404(session, farm_id)
    return FarmSummary.model_validate(farm)


@router.get("/farms/{farm_id}/snapshot", response_model=FarmSnapshot)
async def get_farm_snapshot(farm_id: uuid.UUID, session: DbSession) -> FarmSnapshot:
    """관제 초기 로딩용 통합 스냅샷."""
    return await farm_service.get_farm_snapshot(session, farm_id)


@router.get("/farms/{farm_id}/state", response_model=FarmStateOut)
async def get_farm_state(farm_id: uuid.UUID, session: DbSession) -> FarmStateOut:
    return await farm_service.get_farm_state(session, farm_id)


@router.get("/farms/{farm_id}/sensors", response_model=list[SensorSummary])
async def list_farm_sensors(
    farm_id: uuid.UUID,
    session: DbSession,
) -> list[SensorSummary]:
    return await farm_service.list_farm_sensors(session, farm_id)


@router.get("/farms/{farm_id}/actuators", response_model=list[ActuatorSummary])
async def list_farm_actuators(
    farm_id: uuid.UUID,
    session: DbSession,
) -> list[ActuatorSummary]:
    return await farm_service.list_farm_actuators(session, farm_id)


@router.get("/sensors/{sensor_id}/readings", response_model=list[SensorReadingOut])
async def list_sensor_readings(
    sensor_id: uuid.UUID,
    session: DbSession,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[SensorReadingOut]:
    return await farm_service.list_sensor_readings(session, sensor_id, limit=limit)
