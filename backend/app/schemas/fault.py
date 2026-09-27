"""
센서 고장 주입 API 스키마 (6단계 Day 22).

- POST /simulations/{run_id}/faults                    : 주입 시작
- POST /simulations/{run_id}/faults/{fault_id}/clear   : 해제
- GET  /simulations/{run_id}/faults                    : run 이력
- GET  /farms/{farm_id}/faults                         : 최신 run 이력 (관제 UI)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import FaultType, SensorType


class FaultInjectRequest(BaseModel):
    """
    sensor_id 또는 sensor_type 중 하나로 대상 센서를 고른다.

    magnitude  : spike 가산 크기 (없으면 센서 타입 기본값)
    stuck_value: stuck 고정값 (없으면 주입 시점 최신 측정값)
    """

    sensor_id: uuid.UUID | None = None
    sensor_type: SensorType | None = None
    fault_type: FaultType
    magnitude: float | None = None
    stuck_value: float | None = None
    reason: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _target_required(self) -> FaultInjectRequest:
        if self.sensor_id is None and self.sensor_type is None:
            raise ValueError("sensor_id or sensor_type is required")
        return self


class FaultClearRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class FaultOut(BaseModel):
    id: uuid.UUID
    simulation_run_id: uuid.UUID
    sensor_id: uuid.UUID
    sensor_code: str
    sensor_type: SensorType
    fault_type: FaultType
    active: bool
    magnitude: float | None
    stuck_value: float | None
    start_simulation_time: float
    end_simulation_time: float | None
    started_at: datetime
    cleared_at: datetime | None
    reason: str | None
    notes: str | None


class FaultListOut(BaseModel):
    run_id: uuid.UUID | None
    faults: list[FaultOut]
