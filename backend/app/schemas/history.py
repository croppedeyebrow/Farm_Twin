"""
측정 이력·집계·품질 리포트 스키마 (6단계 Day 23).

bucket_seconds=0  : 원시 행 (count=1, avg=min=max=value, raw/quality 포함)
bucket_seconds>0  : floor(simulation_time / bucket) 구간 집계.
                    avg/min/max 는 good 행만 — 이상치가 추세를 흔들지 않게 한다.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.domain.enums import ReadingQuality, SensorType, SimulationStatus, Unit


class HistoryPoint(BaseModel):
    t: float
    count: int
    avg: float | None
    min: float | None
    max: float | None
    quality_counts: dict[ReadingQuality, int]
    raw_value: float | None = None
    quality: ReadingQuality | None = None
    quality_reason: str | None = None
    source_sequence: int | None = None


class HistorySeries(BaseModel):
    sensor_id: uuid.UUID
    sensor_code: str
    sensor_type: SensorType
    unit: Unit
    points: list[HistoryPoint]


class ReadingHistoryOut(BaseModel):
    run_id: uuid.UUID | None
    bucket_seconds: int
    start_simulation_time: float | None
    end_simulation_time: float | None
    series: list[HistorySeries]


class ReasonCount(BaseModel):
    reason: str
    count: int


class FaultEpisode(BaseModel):
    fault_type: str
    start_simulation_time: float
    end_simulation_time: float | None


class SensorQualityReport(BaseModel):
    sensor_id: uuid.UUID
    sensor_code: str
    sensor_type: SensorType
    total: int
    quality_counts: dict[ReadingQuality, int]
    good_ratio: float | None
    missing_ratio: float | None
    first_simulation_time: float | None
    last_simulation_time: float | None
    top_reasons: list[ReasonCount]
    faults: list[FaultEpisode]


class QualityReportOut(BaseModel):
    run_id: uuid.UUID | None
    run_status: SimulationStatus | None
    generated_at: datetime
    total: int
    quality_counts: dict[ReadingQuality, int]
    good_ratio: float | None
    sensors: list[SensorQualityReport]
