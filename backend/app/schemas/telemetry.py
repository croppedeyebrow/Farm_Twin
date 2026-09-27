"""
Telemetry ingest·센서 품질 API 스키마 (6단계 Day 21).

- POST /simulations/{run_id}/readings : 외부 reading 적재 + 스트림 품질 판정
- GET  /farms/{farm_id}/sensors/health : 센서별 현재 품질 (stale/missing 포함)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import ReadingQuality, SensorType, SimulationStatus, Unit
from app.domain.telemetry import TelemetryReadingIn


class TelemetryIngestRequest(BaseModel):
    readings: list[TelemetryReadingIn] = Field(min_length=1, max_length=1000)


class IngestRejection(BaseModel):
    """적재하지 않은 reading. index 는 요청 readings 배열 위치."""

    index: int
    sensor_type: SensorType
    sequence: int | None
    reason: str


class TelemetryIngestResult(BaseModel):
    run_id: uuid.UUID
    accepted: int
    # 누락 sequence 마다 저장한 quality=missing 마커 행 수
    missing_markers: int
    # 상한 초과로 마커를 만들지 않은 누락 개수
    missing_truncated: int
    rejected: list[IngestRejection]
    quality_counts: dict[ReadingQuality, int]


class SensorHealthOut(BaseModel):
    """
    센서 하나의 현재 품질.

    quality 는 조회 시점 판정(stale/missing 포함), stored_quality 는 최신 행에 저장된 품질.
    value 는 마지막 측정값 — 최신 행이 누락 마커면 그 이전 값이다.
    """

    sensor_id: uuid.UUID
    code: str
    name: str
    sensor_type: SensorType
    unit: Unit
    quality: ReadingQuality
    quality_reason: str | None
    stored_quality: ReadingQuality | None
    value: float | None
    raw_value: float | None
    source_sequence: int | None
    simulation_time: float | None
    ingested_at: datetime | None
    age_simulation_s: float | None
    age_wall_s: float | None
    recent_counts: dict[ReadingQuality, int]


class SensorHealthReport(BaseModel):
    farm_id: uuid.UUID
    run_id: uuid.UUID | None
    run_status: SimulationStatus | None
    current_simulation_time: float | None
    generated_at: datetime
    recent_window: int
    stale_after_simulation_s: float
    stale_ingest_wall_s: float
    summary: dict[ReadingQuality, int]
    sensors: list[SensorHealthOut]
