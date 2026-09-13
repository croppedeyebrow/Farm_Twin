"""
시뮬레이션 run 스키마 (3단계 Day 11).

/simulations 제어·상태 응답용.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import SimulationStatus, WeatherMode


class SimulationRunOut(BaseModel):
    """SimulationRun API 응답."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    farm_id: uuid.UUID
    room_id: uuid.UUID
    name: str
    status: SimulationStatus
    random_seed: int
    weather_mode: WeatherMode
    environment_model_version: str
    simulation_time_seconds: float
    time_scale: float
    started_at: datetime | None = None
    ended_at: datetime | None = None
    notes: str | None = None


class SimulationStepRequest(BaseModel):
    """가상 시계를 N 스텝 전진시키며 참값·readings 를 커밋한다."""

    steps: int = Field(default=1, ge=1, le=3600)
    # 한 스텝당 가상 초 (clock step_seconds * speed 개념의 dt)
    dt_seconds: float = Field(default=60.0, gt=0)
    # True 면 readings 도 batch insert
    persist_readings: bool = True


class SimulationStepResult(BaseModel):
    """step 실행 결과 요약."""

    run_id: uuid.UUID
    status: SimulationStatus
    steps_applied: int
    simulation_time_seconds: float
    farm_state_version: int
    readings_inserted: int
    temperature_c: float
    humidity_pct: float
    co2_ppm: float
    substrate_moisture_pct: float
    ppfd_umol: float
