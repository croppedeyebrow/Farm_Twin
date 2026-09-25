"""
실시간 이벤트 envelope · sequence (5단계 Day 16).

=============================================================================
역할
-----------------------------------------------------------------------------
관제 WebSocket 으로 나가는 **모든** JSON 을 같은 겉봉투로 맞춘다.
클라이언트가 Zod 등으로 런타임 검증하고, sequence 로 누락을 감지할 수 있다.

데이터엔지니어링 설계 4절(텔레메트리 계약)을 관제 WS 에 맞게 축약했다.
센서 reading 전용 필드(value/unit/quality)는 payload 안으로 넣고,
공통 메타만 envelope 상위에 둔다.

=============================================================================
필수 공통 필드
-----------------------------------------------------------------------------
  event_id          메시지 고유 ID (재전송·디듀프용)
  event_type        RealtimeEventType
  schema_version    envelope 필드 계약 ("events.v1")
  farm_id           구독 키 (= ConnectionManager 키)
  sequence          farm 스트림 단조 번호
  occurred_at       wall-clock 발행 시각 (UTC)
  payload           event_type 별 본문 dict

선택 (이벤트에 따라):
  room_id, simulation_run_id, simulation_time (가상 시계 초)

EVENT_SCHEMA_VERSION vs Rule/payload
------------------------------------
- EVENT_SCHEMA_VERSION: **envelope 키 의미** 가 바뀔 때 올린다
- payload 내부 스키마는 event_type 별로 진화 가능 (Day 17+)

두 가지 sequence 를 혼동하지 말 것
----------------------------------
1) EventEnvelope.sequence
   → 관제 WS 스트림 순서 (farm 단위, Day 16 manager 가 발급)
2) sensor_readings.sequence
   → 한 simulation_run 안 측정 행 순서 (DB UNIQUE)

Day 17 복구: WS sequence 가 비면 REST snapshot 으로 latest 를 다시 맞춘다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# envelope 필드 계약 버전 (payload 스키마와 분리해서 올린다)
EVENT_SCHEMA_VERSION = "events.v1"


class RealtimeEventType(StrEnum):
    """
    관제 WebSocket 이벤트 종류 (Day 16 MVP).

    문자열 값은 프론트 Zod enum 과 1:1 로 맞출 예정이다.
    """

    # 연결 직후 1회: 클라이언트가 "지금부터 N 다음을 기대" 하도록 기준점 제공
    # sequence 를 올리지 않는다 (send_connection_ready 참고)
    CONNECTION_READY = "connection.ready"
    # POST .../step commit 후 — FarmState 참값 요약 (SimulationStepResult)
    FARM_STATE_UPDATED = "farm_state.updated"
    # start/pause/resume/stop commit 후 — SimulationRunOut
    SIMULATION_STATUS = "simulation.status"
    # 수동 제어 UI 등 — Actuator 운전 캐시 갱신
    ACTUATOR_UPDATED = "actuator.updated"


class EventEnvelope(BaseModel):
    """
    WS JSON 한 건의 공통 포장.

    extra="forbid": 알 수 없는 상위 키를 거부해 계약 드리프트를 막는다.
    클라이언트는 sequence 단조성을 검사하고,
    누락 시 Day 17 REST snapshot 으로 복구한다.
    """

    model_config = ConfigDict(extra="forbid")

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: RealtimeEventType
    schema_version: str = EVENT_SCHEMA_VERSION
    farm_id: uuid.UUID
    room_id: uuid.UUID | None = None
    simulation_run_id: uuid.UUID | None = None
    # 0 = 아직 본 이벤트 없음(connection.ready 초기). 본 이벤트는 1부터.
    sequence: int = Field(ge=0)
    # 가상 시계(초). wall-clock 인 occurred_at 과 역할이 다르다.
    simulation_time: float | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_message(self) -> dict[str, Any]:
        """
        WebSocket send_json 용 JSON-compatible dict.

        mode="json" → UUID/datetime 을 문자열로 직렬화한다.
        """
        return self.model_dump(mode="json")


def build_envelope(
    *,
    event_type: RealtimeEventType,
    farm_id: uuid.UUID,
    sequence: int,
    payload: dict[str, Any] | None = None,
    room_id: uuid.UUID | None = None,
    simulation_run_id: uuid.UUID | None = None,
    simulation_time: float | None = None,
    occurred_at: datetime | None = None,
) -> EventEnvelope:
    """
    공통 필드가 채워진 envelope 생성 헬퍼.

    publisher / routes 가 직접 EventEnvelope(...) 를 흩뿌리지 않게 한다.
    """
    return EventEnvelope(
        event_type=event_type,
        farm_id=farm_id,
        sequence=sequence,
        payload=payload or {},
        room_id=room_id,
        simulation_run_id=simulation_run_id,
        simulation_time=simulation_time,
        occurred_at=occurred_at or datetime.now(UTC),
    )
