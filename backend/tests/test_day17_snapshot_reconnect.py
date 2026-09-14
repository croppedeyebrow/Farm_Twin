"""
5단계 Day 17 — REST snapshot stream_sequence · 갭 복구 계약 테스트.

검증 축
-------
- FarmSnapshot.stream_sequence 기본값 0
- ConnectionManager 발급 번호가 snapshot 필드에 반영
- (클라 쪽) sequence 갭은 REST snapshot 으로 재정렬 — 서버 replay 버퍼 없음
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.farm import (
    FarmSnapshot,
    FarmSummary,
    RoomSummary,
)
from app.websocket.envelope import RealtimeEventType
from app.websocket.manager import reset_connection_manager
from app.websocket.publisher import publish_event


@pytest.fixture(autouse=True)
def _fresh_manager() -> None:
    reset_connection_manager()


def test_farm_snapshot_stream_sequence_default() -> None:
    farm_id = uuid.uuid4()
    room_id = uuid.uuid4()
    snap = FarmSnapshot(
        farm=FarmSummary(
            id=farm_id,
            site_id=uuid.uuid4(),
            code="f1",
            name="Farm",
        ),
        room=RoomSummary(
            id=room_id,
            farm_id=farm_id,
            code="r1",
            name="Room",
        ),
        racks=[],
        sensors=[],
        actuators=[],
        state=None,
    )
    assert snap.stream_sequence == 0


@pytest.mark.asyncio
async def test_get_farm_snapshot_reads_manager_sequence() -> None:
    """publish 로 sequence 가 올라간 뒤 snapshot 이 같은 번호를 돌려준다."""
    from app.services import farm as farm_service
    from app.websocket.manager import get_connection_manager

    farm_id = uuid.uuid4()
    room_id = uuid.uuid4()
    site_id = uuid.uuid4()

    await publish_event(
        farm_id=farm_id,
        event_type=RealtimeEventType.SIMULATION_STATUS,
        payload={"status": "running"},
    )
    await publish_event(
        farm_id=farm_id,
        event_type=RealtimeEventType.FARM_STATE_UPDATED,
        payload={"temperature_c": 24.0},
    )
    assert get_connection_manager().last_sequence(farm_id) == 2

    farm = MagicMock()
    farm.id = farm_id
    farm.site_id = site_id
    farm.code = "demo"
    farm.name = "Demo"
    farm.description = None

    room = MagicMock()
    room.id = room_id
    room.farm_id = farm_id
    room.code = "room-1"
    room.name = "Room"

    state = MagicMock()
    state.id = uuid.uuid4()
    state.farm_id = farm_id
    state.room_id = room_id
    state.version = 1
    state.temperature_c = 22.0
    state.humidity_pct = 50.0
    state.co2_ppm = 400.0
    state.substrate_moisture_pct = 40.0
    state.ppfd_umol = 0.0
    state.simulation_time = 0.0
    state.updated_at = datetime.now(UTC)

    session = AsyncMock()
    session.get = AsyncMock(return_value=farm)

    async def scalar(stmt: object) -> object:
        # room → state 순으로 호출됨 (대략)
        text = str(stmt)
        if "rooms" in text.lower() or "Room" in text:
            return room
        return state

    # SQLAlchemy select 객체를 문자열로 구분하기 어려워 side_effect 큐 사용
    session.scalar = AsyncMock(side_effect=[room, state])

    empty = MagicMock()
    empty.all = MagicMock(return_value=[])
    session.scalars = AsyncMock(return_value=empty)

    snap = await farm_service.get_farm_snapshot(session, farm_id)
    assert snap.stream_sequence == 2
    assert snap.farm.id == farm_id
    assert snap.state is not None
    assert snap.state.temperature_c == 22.0
