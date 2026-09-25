"""
실시간 이벤트 발행 (5단계 Day 16).

=============================================================================
역할
-----------------------------------------------------------------------------
services (특히 simulation) 가 DB 작업을 끝낸 뒤 호출하는 **유일한** push API.
ConnectionManager / envelope 조립 세부사항은 여기로 감춘다.

=============================================================================
불변조건 (반드시)
-----------------------------------------------------------------------------
  await session.commit()
  await session.refresh(...)
  await publish_* (...)     ← 이 순서만 허용

commit 전 push 금지.
이유: 클라이언트가 WS 로 본 상태가 REST snapshot 과 어긋나면
관제·감사·재현이 전부 깨진다 (시간_컬럼_의미.md).

실패 정책
---------
push 예외는 로그 후 삼킨다 (반환 0).
이미 커밋된 DB 상태는 유지한다.
구독자가 놓친 이벤트는 Day 17 REST snapshot + sequence 복구로 메운다.

connection.ready vs publish_event
---------------------------------
- send_connection_ready: **한 소켓**에만, sequence **미증가**
- publish_event: farm **전체** fan-out, sequence **증가**
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import WebSocket

from app.schemas.simulation import SimulationRunOut, SimulationStepResult
from app.websocket.envelope import RealtimeEventType, build_envelope
from app.websocket.manager import ConnectionManager, get_connection_manager

logger = logging.getLogger(__name__)


async def publish_event(
    *,
    farm_id: uuid.UUID,
    event_type: RealtimeEventType,
    payload: dict[str, Any],
    room_id: uuid.UUID | None = None,
    simulation_run_id: uuid.UUID | None = None,
    simulation_time: float | None = None,
    manager: ConnectionManager | None = None,
) -> int:
    """
    sequence 발급 → envelope 조립 → farm 구독자 broadcast.

    manager 인자를 받는 이유: 단위 테스트에서 전역 싱글톤 대신
    주입한 ConnectionManager 를 쓰기 위함.

    Returns
    -------
    전송 성공 소켓 수. 구독자 없거나 예외 시 0.
    """
    mgr = manager or get_connection_manager()
    try:
        sequence = mgr.next_sequence(farm_id)
        envelope = build_envelope(
            event_type=event_type,
            farm_id=farm_id,
            sequence=sequence,
            payload=payload,
            room_id=room_id,
            simulation_run_id=simulation_run_id,
            simulation_time=simulation_time,
        )
        return await mgr.broadcast(farm_id, envelope.to_message())
    except Exception:
        logger.exception(
            "realtime publish failed farm_id=%s event_type=%s",
            farm_id,
            event_type,
        )
        return 0


async def send_connection_ready(
    farm_id: uuid.UUID,
    websocket: WebSocket,
    *,
    manager: ConnectionManager | None = None,
) -> None:
    """
    새 연결 **하나**에 connection.ready 를 보낸다.

    sequence 를 올리지 않는다.
    payload.last_sequence = 현재까지 발급된 마지막 번호
      → 클라: "다음에 올 본 이벤트의 sequence 는 last+1 이어야 한다"
      → last==0 이면 아직 본 이벤트 없음.
    """
    mgr = manager or get_connection_manager()
    try:
        last = mgr.last_sequence(farm_id)
        envelope = build_envelope(
            event_type=RealtimeEventType.CONNECTION_READY,
            farm_id=farm_id,
            sequence=last,
            payload={"last_sequence": last},
        )
        await websocket.send_json(envelope.to_message())
    except Exception:
        logger.exception("connection.ready send failed farm_id=%s", farm_id)


async def publish_farm_state_updated(
    *,
    farm_id: uuid.UUID,
    room_id: uuid.UUID,
    result: SimulationStepResult,
    manager: ConnectionManager | None = None,
) -> int:
    """
    step commit 이후 FarmState 참값 갱신 이벤트.

    payload 는 SimulationStepResult JSON (온도 등 = 참값, readings 아님).
    services.simulation.step_run 끝에서만 호출한다.
    """
    return await publish_event(
        farm_id=farm_id,
        event_type=RealtimeEventType.FARM_STATE_UPDATED,
        room_id=room_id,
        simulation_run_id=result.run_id,
        simulation_time=result.simulation_time_seconds,
        payload=result.model_dump(mode="json"),
        manager=manager,
    )


async def publish_simulation_status(
    run: SimulationRunOut,
    *,
    manager: ConnectionManager | None = None,
) -> int:
    """
    run 상태 전이 commit 이후 이벤트.

    start / pause / resume / stop 각각의 commit+refresh 직후 호출.
    """
    return await publish_event(
        farm_id=run.farm_id,
        event_type=RealtimeEventType.SIMULATION_STATUS,
        room_id=run.room_id,
        simulation_run_id=run.id,
        simulation_time=run.simulation_time_seconds,
        payload=run.model_dump(mode="json"),
        manager=manager,
    )


async def publish_actuator_updated(
    *,
    farm_id: uuid.UUID,
    room_id: uuid.UUID,
    actuator_payload: dict[str, Any],
    manager: ConnectionManager | None = None,
) -> int:
    """수동 제어 등 Actuator 캐시 commit 이후 이벤트."""
    return await publish_event(
        farm_id=farm_id,
        event_type=RealtimeEventType.ACTUATOR_UPDATED,
        room_id=room_id,
        payload=actuator_payload,
        manager=manager,
    )
