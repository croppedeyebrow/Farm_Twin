"""
run / 이벤트 lineage 스키마 (6단계 Day 23).

run lineage  : 이 run 이 어떤 seed·모델·규칙 묶음·체크포인트로 만들어졌고
               무엇을 얼마나 남겼는지 (재생 원본·재생본 관계 포함)
event lineage: 제어 이벤트 → 명령 → 규칙(명령 당시 개정) → 판정 근거 reading
               → 그 시각 외기 스냅샷 → run
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.domain.enums import SimulationStatus, WeatherMode


class LineageRunRef(BaseModel):
    id: uuid.UUID
    name: str
    status: SimulationStatus
    random_seed: int
    weather_mode: WeatherMode
    environment_model_version: str
    rule_set_version: str | None
    simulation_time_seconds: float
    replay_of_run_id: uuid.UUID | None


class LineageRuleOut(BaseModel):
    id: uuid.UUID
    name: str
    version: int
    enabled: bool
    metric: str
    target_actuator_type: str
    command_count: int


class RunLineageCounts(BaseModel):
    readings: int
    weather_snapshots: int
    rule_commands: int
    manual_commands: int
    blocked_commands: int
    events: int
    faults: int


class RunLineageOut(BaseModel):
    run: LineageRunRef
    started_at: datetime | None
    ended_at: datetime | None
    checkpoint_time: float | None
    telemetry_schema_versions: list[str]
    sensor_model_versions: list[str]
    rules: list[LineageRuleOut]
    counts: RunLineageCounts
    replay_of: LineageRunRef | None
    replays: list[LineageRunRef]


class LineageEventOut(BaseModel):
    id: uuid.UUID
    event_type: str
    message: str | None
    actual_output_ratio: float | None
    simulation_time: float
    recorded_at: datetime


class LineageCommandOut(BaseModel):
    id: uuid.UUID
    origin: str  # rule | manual
    status: str
    reason: str | None
    desired_mode: str
    desired_output_ratio: float
    simulation_time: float
    idempotency_key: str
    actuator_code: str
    actuator_type: str


class LineageRuleRef(BaseModel):
    id: uuid.UUID
    name: str
    version_at_command: int | None
    current_version: int
    metric: str
    comparator: str
    start_threshold: float
    stop_threshold: float


class LineageReadingOut(BaseModel):
    id: uuid.UUID
    sensor_code: str
    sensor_type: str
    source_sequence: int | None
    simulation_time: float
    raw_value: float | None
    value: float | None
    quality: str
    quality_reason: str | None
    telemetry_schema_version: str
    sensor_model_version: str


class LineageWeatherOut(BaseModel):
    sequence: int
    source: WeatherMode
    simulation_time: float
    outdoor_temperature_c: float
    outdoor_humidity_pct: float


class EventLineageOut(BaseModel):
    event: LineageEventOut
    command: LineageCommandOut
    rule: LineageRuleRef | None
    trigger_reading: LineageReadingOut | None
    weather: LineageWeatherOut | None
    run: LineageRunRef
