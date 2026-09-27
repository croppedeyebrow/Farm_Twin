"""
재생 데이터셋·재생 결과 스키마 (6단계 Day 23).

데이터셋(farmtwin.replay.v1)은 원본 run 을 다른 run 으로 다시 돌리는 데 필요한
입력(체크포인트·외기·고장·수동 제어·스텝 간격)과 비교용 기대 결과
(readings·commands)를 한 JSON 으로 묶는다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.enums import (
    ActuatorMode,
    FaultType,
    SimulationStatus,
    WeatherMode,
)

REPLAY_DATASET_FORMAT = "farmtwin.replay.v1"


class ReplayRunMeta(BaseModel):
    id: uuid.UUID
    name: str
    farm_id: uuid.UUID
    room_id: uuid.UUID
    room_code: str
    status: SimulationStatus
    random_seed: int
    weather_mode: WeatherMode
    environment_model_version: str
    rule_set_version: str | None
    simulation_time_seconds: float
    replay_of_run_id: uuid.UUID | None = None


class ReplayRule(BaseModel):
    name: str
    version: int
    enabled: bool
    priority: int
    metric: str
    comparator: str
    start_threshold: float
    stop_threshold: float
    target_actuator_type: str
    target_mode: str
    target_output_ratio: float
    cooldown_seconds: float
    min_on_seconds: float


class ReplayFault(BaseModel):
    sensor_code: str
    fault_type: FaultType
    magnitude: float | None = None
    stuck_value: float | None = None
    start_simulation_time: float
    end_simulation_time: float | None = None
    reason: str | None = None


class ReplayManualAction(BaseModel):
    simulation_time: float
    actuator_code: str
    mode: ActuatorMode
    output_ratio: float = Field(ge=0.0, le=1.0)


class ReplayDataset(BaseModel):
    """
    readings 행: [sensor_code, source_sequence, simulation_time, raw_value, value, quality]
    commands 행: [simulation_time, actuator_code, desired_mode, desired_output_ratio,
                  status, origin(rule 이름 | "manual")]
    weather 행 : [simulation_time, outdoor_temperature_c, outdoor_humidity_pct]
    steps      : [[dt_seconds, 스텝 수], ...] — 원본 스텝 간격 그대로
    """

    format: Literal["farmtwin.replay.v1"]
    exported_at: datetime
    run: ReplayRunMeta
    initial_state: dict[str, Any]
    rules: list[ReplayRule]
    sensor_codes: list[str]
    actuator_codes: list[str]
    steps: list[tuple[float, int]]
    weather: list[tuple[float, float, float]]
    faults: list[ReplayFault]
    manual_actions: list[ReplayManualAction]
    readings: list[tuple[str, int | None, float, float | None, float | None, str]]
    commands: list[tuple[float, str, str, float, str, str]]


class ReplayImportRequest(BaseModel):
    dataset: ReplayDataset
    name: str | None = Field(default=None, max_length=120)


class ReplayRunRequest(BaseModel):
    # 한 요청에서 진행할 최대 스텝 (남은 스텝이 더 많으면 다음 호출로 이어간다)
    max_steps: int = Field(default=5000, ge=1, le=20000)


class ReadingMismatch(BaseModel):
    sensor_code: str
    source_sequence: int | None
    simulation_time: float
    expected: list[Any] | None
    actual: list[Any] | None


class CommandMismatch(BaseModel):
    index: int
    expected: list[Any] | None
    actual: list[Any] | None


class ReplayCompareOut(BaseModel):
    run_id: uuid.UUID
    source_run_id: uuid.UUID
    status: SimulationStatus
    checkpoint_time: float
    simulation_time_seconds: float
    end_simulation_time: float
    completed: bool
    rule_set_version_expected: str | None
    rule_set_version_actual: str | None
    rule_set_match: bool
    readings_expected: int
    readings_actual: int
    readings_matched: int
    readings_mismatched: int
    readings_missing: int
    readings_extra: int
    commands_expected: int
    commands_actual: int
    commands_matched: bool
    reproduced: bool
    reading_mismatches: list[ReadingMismatch]
    command_mismatches: list[CommandMismatch]


class ReplayRunOut(BaseModel):
    run_id: uuid.UUID
    steps_applied: int
    steps_remaining: int
    paused_run_ids: list[uuid.UUID]
    compare: ReplayCompareOut
