"""
시뮬레이션 run 스키마 (3단계 Day 11).

/simulations 제어·상태·step 결과의 요청/응답 JSON 계약.
ORM 엔티티를 그대로 노출하지 않고 Pydantic 으로 경계를 고정한다.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import SimulationStatus, WeatherMode


class SimulationRunOut(BaseModel):
    """
    SimulationRun API 응답.

    simulation_time_seconds: 가상 시계 (상태전이 기준).
    started_at / ended_at: wall-clock (운영 관측용, 가상 시계와 별개).
    random_seed: 외기·센서 노이즈 재현성 키.
    """

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
    """
    가상 시계를 N 스텝 전진시키며 참값·(옵션) readings 를 커밋한다.

    steps × dt_seconds = 이번 요청이 진행하는 가상 시간.
    예) steps=60, dt=60 → 1시간 가상 시계열 (3단계 완료 기준 데모).
    """

    steps: int = Field(default=1, ge=1, le=3600)
    # 한 스텝당 가상 초 (SimulationClock 의 step×speed 와 같은 역할의 dt)
    dt_seconds: float = Field(default=60.0, gt=0)
    # False 면 FarmState 만 갱신 (재현성 테스트·부하 감소용)
    persist_readings: bool = True


class SimulationStepResult(BaseModel):
    """
    step 실행 결과 요약.

    temperature_c 등 환경 필드는 **FarmState 참값**이다.
    readings_inserted 만 측정값 적재 건수를 알려 준다.
    """

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
