"""Farm / snapshot 응답 스키마 (2단계 Day 7)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.enums import (
    ActuatorMode,
    ActuatorType,
    ReadingQuality,
    ReadingSource,
    SensorType,
    Unit,
)


class FarmSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_id: uuid.UUID
    code: str
    name: str
    description: str | None = None


class RoomSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    farm_id: uuid.UUID
    code: str
    name: str


class RackSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    room_id: uuid.UUID
    code: str
    name: str
    position_x: float | None = None
    position_y: float | None = None
    position_z: float | None = None


class SensorSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    room_id: uuid.UUID
    rack_id: uuid.UUID | None
    code: str
    name: str
    sensor_type: SensorType
    unit: Unit
    model_version: str


class ActuatorSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    room_id: uuid.UUID
    code: str
    name: str
    actuator_type: ActuatorType
    mode: ActuatorMode
    output_ratio: float


class FarmStateOut(BaseModel):
    """환경 참값 스냅샷."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    farm_id: uuid.UUID
    room_id: uuid.UUID
    version: int
    temperature_c: float
    humidity_pct: float
    co2_ppm: float
    substrate_moisture_pct: float
    ppfd_umol: float
    simulation_time: float
    updated_at: datetime


class SensorReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sensor_id: uuid.UUID
    sequence: int
    value: float
    unit: Unit
    quality: ReadingQuality
    source: ReadingSource
    simulation_time: float
    sampled_at: datetime
    ingested_at: datetime


class FarmSnapshot(BaseModel):
    """관제 초기 로딩용 통합 스냅샷 (참값 + 메타)."""

    farm: FarmSummary
    room: RoomSummary
    racks: list[RackSummary]
    sensors: list[SensorSummary]
    actuators: list[ActuatorSummary]
    state: FarmStateOut | None
