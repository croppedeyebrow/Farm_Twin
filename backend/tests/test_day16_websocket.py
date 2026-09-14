"""
5단계 Day 16 — WebSocket manager · envelope/sequence · commit 후 push.

검증 축
-------
- EventEnvelope 필수 필드·schema_version (events.v1)
- ConnectionManager sequence 단조 증가·farm 별 fan-out
- /ws/farms/{id} 연결 시 connection.ready (sequence 미증가)
- start_run: commit 호출이 publish 보다 앞선다 (순서 mock)
- publish 예외는 swallow (API/커밋 결과를 뒤집지 않음)

DB 통합은 Day 11 테스트·Day 17 snapshot 복구에서 이어진다.
이 파일은 순수 WS 계약·매니저·commit-then-push 불변조건을 단위로 증명한다.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketState

from app.domain.enums import SimulationStatus, WeatherMode
from app.main import app
from app.schemas.simulation import SimulationRunOut, SimulationStepResult
from app.websocket.envelope import (
    EVENT_SCHEMA_VERSION,
    RealtimeEventType,
    build_envelope,
)
from app.websocket.manager import ConnectionManager, reset_connection_manager
from app.websocket.publisher import (
    publish_event,
    publish_farm_state_updated,
    publish_simulation_status,
    send_connection_ready,
)


@pytest.fixture(autouse=True)
def _fresh_manager() -> ConnectionManager:
    """테스트마다 연결·sequence 격리."""
    return reset_connection_manager()


def test_envelope_schema_version_and_required_fields() -> None:
    farm_id = uuid.uuid4()
    envelope = build_envelope(
        event_type=RealtimeEventType.FARM_STATE_UPDATED,
        farm_id=farm_id,
        sequence=1,
        payload={"temperature_c": 24.0},
    )
    assert envelope.schema_version == EVENT_SCHEMA_VERSION
    message = envelope.to_message()
    for key in (
        "event_id",
        "event_type",
        "schema_version",
        "farm_id",
        "sequence",
        "occurred_at",
        "payload",
    ):
        assert key in message
    assert message["event_type"] == "farm_state.updated"
    assert message["sequence"] == 1
    assert message["farm_id"] == str(farm_id)


def test_connection_manager_sequence_is_monotonic() -> None:
    manager = ConnectionManager()
    farm_id = uuid.uuid4()
    assert manager.last_sequence(farm_id) == 0
    assert manager.next_sequence(farm_id) == 1
    assert manager.next_sequence(farm_id) == 2
    assert manager.last_sequence(farm_id) == 2


@pytest.mark.asyncio
async def test_broadcast_fans_out_to_subscribers() -> None:
    manager = ConnectionManager()
    farm_id = uuid.uuid4()
    other_farm = uuid.uuid4()

    ws_a = AsyncMock()
    ws_a.client_state = WebSocketState.CONNECTED
    ws_b = AsyncMock()
    ws_b.client_state = WebSocketState.CONNECTED
    ws_other = AsyncMock()
    ws_other.client_state = WebSocketState.CONNECTED

    manager._connections[farm_id].add(ws_a)
    manager._connections[farm_id].add(ws_b)
    manager._connections[other_farm].add(ws_other)

    sent = await manager.broadcast(farm_id, {"hello": 1})
    assert sent == 2
    ws_a.send_json.assert_awaited_once_with({"hello": 1})
    ws_b.send_json.assert_awaited_once_with({"hello": 1})
    ws_other.send_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_connection_ready_does_not_advance_sequence(
    _fresh_manager: ConnectionManager,
) -> None:
    farm_id = uuid.uuid4()
    _fresh_manager.next_sequence(farm_id)  # → 1
    websocket = AsyncMock()
    await send_connection_ready(farm_id, websocket, manager=_fresh_manager)
    assert _fresh_manager.last_sequence(farm_id) == 1
    message = websocket.send_json.await_args.args[0]
    assert message["event_type"] == RealtimeEventType.CONNECTION_READY.value
    assert message["sequence"] == 1
    assert message["payload"]["last_sequence"] == 1


@pytest.mark.asyncio
async def test_publish_event_increments_sequence(
    _fresh_manager: ConnectionManager,
) -> None:
    farm_id = uuid.uuid4()
    n1 = await publish_event(
        farm_id=farm_id,
        event_type=RealtimeEventType.SIMULATION_STATUS,
        payload={"status": "running"},
        manager=_fresh_manager,
    )
    n2 = await publish_event(
        farm_id=farm_id,
        event_type=RealtimeEventType.SIMULATION_STATUS,
        payload={"status": "paused"},
        manager=_fresh_manager,
    )
    assert n1 == 0 and n2 == 0
    assert _fresh_manager.last_sequence(farm_id) == 2


def test_ws_farms_sends_connection_ready() -> None:
    farm_id = uuid.uuid4()
    client = TestClient(app)
    with client.websocket_connect(f"/ws/farms/{farm_id}") as websocket:
        message = websocket.receive_json()
        assert message["event_type"] == "connection.ready"
        assert message["schema_version"] == EVENT_SCHEMA_VERSION
        assert message["farm_id"] == str(farm_id)
        assert message["sequence"] == 0
        assert message["payload"]["last_sequence"] == 0


@pytest.mark.asyncio
async def test_publish_simulation_status_payload_shape(
    _fresh_manager: ConnectionManager,
) -> None:
    run = SimulationRunOut(
        id=uuid.uuid4(),
        farm_id=uuid.uuid4(),
        room_id=uuid.uuid4(),
        name="demo",
        status=SimulationStatus.RUNNING,
        random_seed=1,
        weather_mode=WeatherMode.SYNTHETIC,
        environment_model_version="env.v1",
        simulation_time_seconds=120.0,
        time_scale=1.0,
    )
    ws = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED
    _fresh_manager._connections[run.farm_id].add(ws)

    await publish_simulation_status(run, manager=_fresh_manager)
    message = ws.send_json.await_args.args[0]
    assert message["event_type"] == "simulation.status"
    assert message["sequence"] == 1
    assert message["payload"]["status"] == "running"
    assert message["simulation_time"] == 120.0


@pytest.mark.asyncio
async def test_publish_farm_state_updated_uses_step_result(
    _fresh_manager: ConnectionManager,
) -> None:
    farm_id = uuid.uuid4()
    room_id = uuid.uuid4()
    result = SimulationStepResult(
        run_id=uuid.uuid4(),
        status=SimulationStatus.RUNNING,
        steps_applied=1,
        simulation_time_seconds=60.0,
        farm_state_version=2,
        readings_inserted=5,
        temperature_c=24.5,
        humidity_pct=55.0,
        co2_ppm=800.0,
        substrate_moisture_pct=40.0,
        ppfd_umol=200.0,
    )
    ws = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED
    _fresh_manager._connections[farm_id].add(ws)

    await publish_farm_state_updated(
        farm_id=farm_id,
        room_id=room_id,
        result=result,
        manager=_fresh_manager,
    )
    message = ws.send_json.await_args.args[0]
    assert message["event_type"] == "farm_state.updated"
    assert message["payload"]["temperature_c"] == 24.5
    assert message["sequence"] == 1


@pytest.mark.asyncio
async def test_start_run_publishes_only_after_commit() -> None:
    """commit 이 publish_simulation_status 보다 먼저 호출되는지 순서 검증."""
    order: list[str] = []

    session = AsyncMock()

    async def commit() -> None:
        order.append("commit")

    async def refresh(_obj: object) -> None:
        pass

    session.commit = commit
    session.refresh = refresh

    run = MagicMock()
    run.id = uuid.uuid4()
    run.farm_id = uuid.uuid4()
    run.room_id = uuid.uuid4()
    run.status = SimulationStatus.CREATED
    run.started_at = None
    run.ended_at = None
    run.name = "demo"
    run.random_seed = 1
    run.weather_mode = WeatherMode.SYNTHETIC
    run.environment_model_version = "env.v1"
    run.simulation_time_seconds = 0.0
    run.time_scale = 1.0
    run.notes = None

    async def fake_publish(_out: object) -> int:
        order.append("publish")
        return 0

    with (
        patch(
            "app.services.simulation.get_run_or_404",
            new=AsyncMock(return_value=run),
        ),
        patch(
            "app.services.simulation.publish_simulation_status",
            new=fake_publish,
        ),
    ):
        from app.services.simulation import start_run

        await start_run(session, run.id)

    assert order == ["commit", "publish"]


@pytest.mark.asyncio
async def test_publish_failure_is_swallowed(
    _fresh_manager: ConnectionManager,
) -> None:
    farm_id = uuid.uuid4()

    def boom(_farm_id: uuid.UUID) -> int:
        raise RuntimeError("socket down")

    _fresh_manager.next_sequence = boom  # type: ignore[method-assign]
    sent = await publish_event(
        farm_id=farm_id,
        event_type=RealtimeEventType.FARM_STATE_UPDATED,
        payload={},
        manager=_fresh_manager,
    )
    assert sent == 0
