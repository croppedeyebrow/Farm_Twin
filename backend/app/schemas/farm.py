"""
Farm / snapshot 응답 스키마 (2단계 Day 7).

ORM 엔티티를 API JSON 으로 변환한다.
`from_attributes=True` 로 SQLAlchemy 모델 → Pydantic 매핑을 허용한다.

주의: FarmStateOut 은 **참값**, SensorReadingOut 은 **측정값** 이다.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    ActuatorMode,
    ActuatorType,
    ReadingQuality,
    ReadingSource,
    SensorType,
    Unit,
)


class FarmSummary(BaseModel):
    """농장 목록/상세용 요약."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_id: uuid.UUID
    code: str
    name: str
    description: str | None = None


class RoomSummary(BaseModel):
    """재배실 요약."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    farm_id: uuid.UUID
    code: str
    name: str


class RackSummary(BaseModel):
    """랙 요약. position_* 는 3D 배치용 선택 좌표."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    room_id: uuid.UUID
    code: str
    name: str
    position_x: float | None = None
    position_y: float | None = None
    position_z: float | None = None


class SensorSummary(BaseModel):
    """센서 메타. 시계열 값은 readings API 로 분리."""

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
    """액추에이터 메타 + 현재 운전 캐시."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    room_id: uuid.UUID
    code: str
    name: str
    actuator_type: ActuatorType
    mode: ActuatorMode
    output_ratio: float


class ManualActuatorSet(BaseModel):
    """
    운영자 수동 출력 설정 (트윈 대시보드).

    output_ratio=0 → mode=OFF, 그 외 → mode=MANUAL.
    """

    output_ratio: float = Field(ge=0.0, le=1.0)


class FarmStateOut(BaseModel):
    """환경 참값 스냅샷 (farm_states)."""

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
    """가상 센서 측정값 한 점 (sensor_readings)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sensor_id: uuid.UUID
    sequence: int
    value: float  # normalized
    raw_value: float
    unit: Unit
    input_unit: Unit
    quality: ReadingQuality
    quality_reason: str | None = None
    telemetry_schema_version: str
    source: ReadingSource
    simulation_time: float
    sampled_at: datetime
    ingested_at: datetime


class ZoneStateOut(BaseModel):
    """
    작물 구역 참값·파생 요약.

    목적: 딸기/포도 setpoint·근권·병해·추정 Brix를 룸 KPI와 분리해 UI에 노출.
    estimated_brix 는 추정 — 실측 당도와 혼동 금지.
    """

    zone_id: str
    crop: str
    label: str
    air_temperature_c: float
    relative_humidity_pct: float
    co2_ppm: float
    ppfd: float
    vpd_kpa: float
    dli_today: float
    substrate_vwc_pct: float
    substrate_ec: float
    substrate_temperature_c: float
    nutrient_ph: float
    nutrient_ec: float
    leaf_wetness_minutes: float
    irrigation_flow_lpm: float
    drainage_ratio_pct: float
    water_stress_score: float
    disease_risk_score: float
    fruit_maturity_score: float
    estimated_brix: float
    irrigation_valve_open: bool
    simulation_time: float


class FarmZonesOut(BaseModel):
    """
    Farm 내 재배 구역 묶음 + 공유 제어 요구.

    disease_mitigation_active / led_demand_ratio 는 구역 루프가 낸
    설비 요구(max-merge 전 요약)이다.
    """

    strawberry: ZoneStateOut
    grape: ZoneStateOut
    disease_mitigation_active: bool = False
    led_demand_ratio: float = 0.0
    last_irrigation_reason: str = ""
    last_disease_reason: str = ""
    last_led_reason: str = ""


class FarmSnapshot(BaseModel):
    """
    관제 초기·복구용 통합 스냅샷 (2단계 Day 7, 5단계 Day 17 확장).

    REST 로 메타+참값을 한 번에 받고, 이후 증분은 WebSocket 으로 간다.

    stream_sequence (Day 17)
    ------------------------
    이 API 프로세스가 해당 farm 에 대해 **이미 발급한** WS sequence.
    클라이언트는 snapshot 적용 후 `last_sequence = stream_sequence` 로 맞추고,
    다음 본 이벤트는 stream_sequence+1 을 기대한다.

    주의: ConnectionManager 는 프로세스 메모리다 (단일 워커 MVP).
    멀티 인스턴스면 공유 저장소로 옮겨야 한다.
    """

    farm: FarmSummary
    room: RoomSummary
    racks: list[RackSummary]
    sensors: list[SensorSummary]
    actuators: list[ActuatorSummary]
    state: FarmStateOut | None
    zones: FarmZonesOut | None = None
    # Day 17: WS 스트림 정렬용 (없으면 클라가 connection.ready 만으로도 동작 가능)
    stream_sequence: int = 0


class ControlEventOut(BaseModel):
    """
    관제 이벤트 타임라인 한 줄 (5단계 Day 18).

    ControlEvent(결과) + Command/Actuator 요약.
    Command 행을 덮어쓰지 않는 append-only 이력을 UI 가 읽기 좋게 투영한다.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    message: str | None = None
    actual_output_ratio: float | None = None
    simulation_time: float
    recorded_at: datetime
    command_id: uuid.UUID
    simulation_run_id: uuid.UUID
    actuator_code: str | None = None
    actuator_type: str | None = None
    desired_mode: str | None = None
    command_status: str | None = None
