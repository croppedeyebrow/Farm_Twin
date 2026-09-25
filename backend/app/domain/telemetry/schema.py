"""
Telemetry reading 계약 (6단계 Day 20).

schema_version
--------------
- envelope 수준: events.v1 (WebSocket 래퍼)
- reading 수준: telemetry.reading.v1 (측정 페이로드 계약)

이 모듈은 reading 수준 계약만 다룬다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import ReadingQuality, ReadingSource, SensorType, Unit

TELEMETRY_READING_SCHEMA_VERSION: Literal["telemetry.reading.v1"] = (
    "telemetry.reading.v1"
)


class TelemetryReadingIn(BaseModel):
    """
    적재 직전 입력 계약 (ingest).

    - raw_value / input_unit: 센서가 보낸 원본 (덮어쓰지 않음)
    - schema_version 불일치·금지 필드는 거부 (extra=forbid)
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["telemetry.reading.v1"] = TELEMETRY_READING_SCHEMA_VERSION
    sensor_type: SensorType
    raw_value: float
    input_unit: Unit
    source: ReadingSource = ReadingSource.SIMULATED
    simulation_time: float = Field(ge=0.0)
    sampled_at: datetime | None = None
    sensor_id: UUID | None = None
    farm_id: UUID | None = None
    room_id: UUID | None = None
    simulation_run_id: UUID | None = None
    sensor_model_version: str = "v1"


class TelemetryReadingNormalized(BaseModel):
    """
    정규화·품질 판정 후 결과.

    - normalized_value / unit: 저장·규칙·관제에 쓰는 값
    - raw_value / input_unit: 원본 보존
    - quality_reason: Day 20은 clamp·unit 사유, Day 21+ 확장
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["telemetry.reading.v1"] = TELEMETRY_READING_SCHEMA_VERSION
    sensor_type: SensorType
    raw_value: float
    input_unit: Unit
    normalized_value: float
    unit: Unit
    quality: ReadingQuality
    quality_reason: str | None = None
    source: ReadingSource
    simulation_time: float
    sampled_at: datetime | None = None
    sensor_id: UUID | None = None
    farm_id: UUID | None = None
    room_id: UUID | None = None
    simulation_run_id: UUID | None = None
    sensor_model_version: str = "v1"
