"""
6단계 Day 23 — replay dataset·lineage·1분 집계·품질 리포트.

검증 의도
---------
- 규칙 묶음 지문은 결정 필드가 같으면 같고 바뀌면 달라진다
- 해제된 고장은 해제 시각 이후 스텝에 적용되지 않는다 (시각 기반 일정)
- run 체크포인트·외기 스냅샷·규칙 명령의 개정 번호·판정 근거 reading 이 남는다
- 수동 제어도 명령·이벤트로 기록된다
- export → import → run 하면 중간 시각 체크포인트·고장·수동 제어가 있어도
  readings·명령이 원본과 같다 (reproduced)
- 이벤트에서 run 까지 lineage 를 거슬러 올라갈 수 있다
- 1분/5분 집계와 품질 리포트가 원시 행 수·품질 분포와 맞다
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import (
    Actuator,
    ControlCommand,
    ControlEvent,
    FarmState,
    SimulationRun,
    WeatherSnapshot,
)
from app.db.seed import FARM_ID, ROOM_ID, RUN_ID, seed_mvp
from app.db.session import SessionLocal
from app.domain.control.schema import RuleDefinition, RuleSet
from app.domain.enums import (
    ActuatorMode,
    ActuatorType,
    FaultType,
    RuleComparator,
    SensorType,
)
from app.domain.simulation.faults import ActiveFault, FaultSchedule
from app.main import app
from app.services.room_control import clear_blocked_cache
from app.services.sender import SENDER_SEQUENCES

# ---------------------------------------------------------------------------
# 도메인
# ---------------------------------------------------------------------------


def _rule(**overrides: object) -> RuleDefinition:
    base: dict[str, object] = {
        "name": "cool",
        "version": 1,
        "enabled": True,
        "priority": 10,
        "metric": SensorType.TEMPERATURE,
        "comparator": RuleComparator.GT,
        "start_threshold": 28.0,
        "stop_threshold": 26.0,
        "target_actuator_type": ActuatorType.HVAC,
        "target_mode": ActuatorMode.ON,
        "target_output_ratio": 0.8,
    }
    base.update(overrides)
    return RuleDefinition(**base)


def test_rule_set_fingerprint_tracks_decision_fields() -> None:
    first = RuleSet(rules=(_rule(),)).fingerprint()
    assert first.startswith("rules.v1:")
    assert RuleSet(rules=(_rule(description="설명만 변경"),)).fingerprint() == first
    assert RuleSet(rules=(_rule(start_threshold=29.0),)).fingerprint() != first
    # 비활성 규칙은 지문에 들어가지 않는다
    disabled = _rule(name="off", enabled=False)
    assert RuleSet(rules=(_rule(), disabled)).fingerprint() == first


def test_fault_schedule_respects_end_time() -> None:
    fault = ActiveFault(
        sensor_type=SensorType.TEMPERATURE,
        fault_type=FaultType.STUCK,
        start_simulation_time=120.0,
        stuck_value=21.0,
        end_simulation_time=240.0,
    )
    schedule = FaultSchedule(faults=(fault,))
    assert schedule.active_at(60.0) == {}
    assert SensorType.TEMPERATURE in schedule.active_at(180.0)
    assert SensorType.TEMPERATURE in schedule.active_at(240.0)
    assert schedule.active_at(300.0) == {}


# ---------------------------------------------------------------------------
# DB 통합
# ---------------------------------------------------------------------------


@pytest.fixture
async def seeded_farm(require_postgres: None) -> None:
    await seed_mvp(force=True)
    SENDER_SEQUENCES.clear()
    clear_blocked_cache()


@pytest.fixture
async def api_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _step(client: AsyncClient, steps: int = 1, run_id: uuid.UUID = RUN_ID) -> dict:
    response = await client.post(
        f"/simulations/{run_id}/step",
        json={"steps": steps, "dt_seconds": 60.0},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _inject(client: AsyncClient, **body: object) -> dict:
    response = await client.post(f"/simulations/{RUN_ID}/faults", json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def _set_true_temperature(value: float) -> None:
    async with SessionLocal() as session:
        state = await session.scalar(select(FarmState).where(FarmState.room_id == ROOM_ID))
        assert state is not None
        state.temperature_c = value
        await session.commit()


async def _actuator(actuator_type: ActuatorType) -> Actuator:
    async with SessionLocal() as session:
        actuator = await session.scalar(
            select(Actuator).where(
                Actuator.room_id == ROOM_ID,
                Actuator.actuator_type == actuator_type,
            )
        )
        assert actuator is not None
        return actuator


async def _drop_checkpoint() -> None:
    """Day 23 이전부터 진행 중이던 run 처럼 — 다음 스텝에서 중간 시각 체크포인트."""
    async with SessionLocal() as session:
        run = await session.get(SimulationRun, RUN_ID)
        assert run is not None
        run.initial_state = None
        await session.commit()


@pytest.mark.asyncio
async def test_step_records_checkpoint_weather_and_lineage_fields(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    await api_client.post(f"/simulations/{RUN_ID}/start")
    await _set_true_temperature(30.0)
    await _step(api_client, 3)

    async with SessionLocal() as session:
        run = await session.get(SimulationRun, RUN_ID)
        assert run is not None
        assert run.initial_state is not None
        assert run.initial_state["simulation_time"] == 0.0
        assert run.initial_state["farm_state"]["temperature_c"] == 30.0
        assert run.rule_set_version and run.rule_set_version.startswith("rules.v1:")

        snapshots = (
            await session.scalars(
                select(WeatherSnapshot)
                .where(WeatherSnapshot.simulation_run_id == RUN_ID)
                .order_by(WeatherSnapshot.sequence)
            )
        ).all()
        assert [row.sequence for row in snapshots] == [1, 2, 3]
        assert [row.simulation_time for row in snapshots] == [60.0, 120.0, 180.0]

        commands = (
            await session.scalars(
                select(ControlCommand).where(
                    ControlCommand.simulation_run_id == RUN_ID,
                    ControlCommand.rule_id.is_not(None),
                )
            )
        ).all()
        assert commands, "냉방 규칙이 동작해야 한다"
        assert all(command.rule_version == 1 for command in commands)
        assert all(command.trigger_reading_id is not None for command in commands)

    run_out = (await api_client.get(f"/simulations/{RUN_ID}")).json()
    assert run_out["rule_set_version"].startswith("rules.v1:")


@pytest.mark.asyncio
async def test_manual_control_is_recorded_on_active_run(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    led = await _actuator(ActuatorType.LED)

    # run 이 시작 전이면 이력 없이 설비만 바뀐다
    await api_client.post(f"/actuators/{led.id}/manual", json={"output_ratio": 0.4})
    await api_client.post(f"/simulations/{RUN_ID}/start")
    await _step(api_client, 2)
    await api_client.post(f"/actuators/{led.id}/manual", json={"output_ratio": 0.7})
    await api_client.post(f"/actuators/{led.id}/manual", json={"output_ratio": 0.0})

    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(ControlCommand, ControlEvent)
                .join(ControlEvent, ControlEvent.command_id == ControlCommand.id)
                .where(
                    ControlCommand.simulation_run_id == RUN_ID,
                    ControlCommand.reason == "manual",
                )
                .order_by(ControlCommand.issued_at)
            )
        ).all()
    assert len(rows) == 2
    (on_cmd, on_event), (off_cmd, off_event) = rows
    assert on_cmd.rule_id is None
    assert on_cmd.simulation_time == 120.0
    assert on_cmd.desired_mode is ActuatorMode.MANUAL
    assert on_cmd.desired_output_ratio == 0.7
    assert on_event.event_type.value == "applied"
    assert "수동 제어" in (on_event.message or "")
    assert off_cmd.desired_mode is ActuatorMode.OFF
    assert off_event.event_type.value == "stopped"

    events = (await api_client.get(f"/farms/{FARM_ID}/events")).json()
    assert sum(1 for event in events if "수동 제어" in (event["message"] or "")) == 2


async def _build_source_run(client: AsyncClient) -> None:
    await client.post(f"/simulations/{RUN_ID}/start")
    await _step(client, 2)
    dropout = await _inject(client, sensor_type="humidity", fault_type="dropout")
    await _step(client, 2)
    await _set_true_temperature(30.0)

    # 체크포인트를 t=240 (dropout 진행 중, 송신 커서가 수신측보다 앞선 상태) 에서 잡는다
    await _drop_checkpoint()
    await _step(client, 2)

    cleared = await client.post(f"/simulations/{RUN_ID}/faults/{dropout['id']}/clear")
    assert cleared.status_code == 200
    await _step(client, 2)

    await _inject(client, sensor_type="temperature", fault_type="spike")
    await _step(client, 3)

    led = await _actuator(ActuatorType.LED)
    manual = await client.post(f"/actuators/{led.id}/manual", json={"output_ratio": 0.5})
    assert manual.status_code == 200
    await _step(client, 3)


@pytest.mark.asyncio
async def test_replay_reproduces_source_run(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    await _build_source_run(api_client)

    exported = await api_client.get(f"/simulations/{RUN_ID}/dataset")
    assert exported.status_code == 200, exported.text
    dataset = exported.json()
    assert dataset["format"] == "farmtwin.replay.v1"
    assert dataset["initial_state"]["simulation_time"] == 240.0
    assert dataset["steps"] == [[60.0, 10]]
    assert len(dataset["weather"]) == 10
    assert {fault["fault_type"] for fault in dataset["faults"]} == {"dropout", "spike"}
    assert [action["actuator_code"] for action in dataset["manual_actions"]] == [
        next(code for code in dataset["actuator_codes"] if "led" in code.lower())
    ]
    assert any(row[5] == "missing" for row in dataset["readings"])
    assert any(row[5] == "manual" for row in dataset["commands"])
    assert any(row[5] == "cool_on_high_temp" for row in dataset["commands"])

    imported = await api_client.post("/simulations/replay", json={"dataset": dataset})
    assert imported.status_code == 201, imported.text
    replay = imported.json()
    assert replay["replay_of_run_id"] == str(RUN_ID)
    assert replay["weather_mode"] == "REPLAY"
    assert replay["simulation_time_seconds"] == 240.0

    # 원본은 RUNNING 이라 재생 전에 일시정지된다
    ran = await api_client.post(f"/simulations/{replay['id']}/replay/run", json={})
    assert ran.status_code == 200, ran.text
    body = ran.json()
    assert body["paused_run_ids"] == [str(RUN_ID)]
    assert body["steps_applied"] == 10
    assert body["steps_remaining"] == 0

    compare = body["compare"]
    assert compare["reading_mismatches"] == []
    assert compare["command_mismatches"] == []
    assert compare["readings_expected"] == len(dataset["readings"])
    assert compare["readings_missing"] == 0
    assert compare["readings_extra"] == 0
    assert compare["commands_expected"] == len(dataset["commands"])
    assert compare["rule_set_match"] is True
    assert compare["completed"] is True
    assert compare["reproduced"] is True
    assert compare["status"] == "stopped"

    again = await api_client.get(f"/simulations/{replay['id']}/replay/compare")
    assert again.json()["reproduced"] is True

    lineage = (await api_client.get(f"/simulations/{RUN_ID}/lineage")).json()
    assert [item["id"] for item in lineage["replays"]] == [replay["id"]]
    assert lineage["checkpoint_time"] == 240.0
    assert lineage["counts"]["manual_commands"] == 1
    assert lineage["counts"]["faults"] == 2

    replay_lineage = (await api_client.get(f"/simulations/{replay['id']}/lineage")).json()
    assert replay_lineage["replay_of"]["id"] == str(RUN_ID)


@pytest.mark.asyncio
async def test_replay_run_in_chunks_matches(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    await _build_source_run(api_client)
    dataset = (await api_client.get(f"/simulations/{RUN_ID}/dataset")).json()
    replay = (await api_client.post("/simulations/replay", json={"dataset": dataset})).json()

    first = (
        await api_client.post(f"/simulations/{replay['id']}/replay/run", json={"max_steps": 4})
    ).json()
    assert first["steps_applied"] == 4
    assert first["steps_remaining"] == 6
    assert first["compare"]["completed"] is False
    assert first["compare"]["reading_mismatches"] == []

    second = (
        await api_client.post(f"/simulations/{replay['id']}/replay/run", json={})
    ).json()
    assert second["steps_remaining"] == 0
    assert second["compare"]["reproduced"] is True


@pytest.mark.asyncio
async def test_replay_detects_divergence(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    await _build_source_run(api_client)
    dataset = (await api_client.get(f"/simulations/{RUN_ID}/dataset")).json()
    dataset["run"]["random_seed"] = 7
    replay = (await api_client.post("/simulations/replay", json={"dataset": dataset})).json()

    compare = (
        await api_client.post(f"/simulations/{replay['id']}/replay/run", json={})
    ).json()["compare"]
    assert compare["completed"] is True
    assert compare["readings_mismatched"] > 0
    assert compare["reading_mismatches"]
    assert compare["reproduced"] is False


@pytest.mark.asyncio
async def test_replay_import_validation(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    no_checkpoint = await api_client.get(f"/simulations/{RUN_ID}/dataset")
    assert no_checkpoint.status_code == 409

    await api_client.post(f"/simulations/{RUN_ID}/start")
    await _step(api_client, 2)
    dataset = (await api_client.get(f"/simulations/{RUN_ID}/dataset")).json()

    bad_format = {**dataset, "format": "other.v1"}
    assert (
        await api_client.post("/simulations/replay", json={"dataset": bad_format})
    ).status_code == 422

    unknown_sensor = {
        **dataset,
        "readings": [["NOPE-1", 1, 60.0, 1.0, 1.0, "good"], *dataset["readings"]],
    }
    response = await api_client.post("/simulations/replay", json={"dataset": unknown_sensor})
    assert response.status_code == 422
    assert "NOPE-1" in response.text

    not_replay = await api_client.post(f"/simulations/{RUN_ID}/replay/run", json={})
    assert not_replay.status_code == 409


@pytest.mark.asyncio
async def test_event_lineage_walks_back_to_run(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    await api_client.post(f"/simulations/{RUN_ID}/start")
    await _set_true_temperature(30.0)
    await _step(api_client, 2)

    events = (await api_client.get(f"/farms/{FARM_ID}/events")).json()
    rule_event = next(event for event in events if event["actuator_type"] == "hvac")
    response = await api_client.get(f"/control-events/{rule_event['id']}/lineage")
    assert response.status_code == 200, response.text
    lineage = response.json()

    assert lineage["command"]["origin"] == "rule"
    assert lineage["rule"]["name"] == "cool_on_high_temp"
    assert lineage["rule"]["version_at_command"] == 1
    reading = lineage["trigger_reading"]
    assert reading["sensor_type"] == "temperature"
    assert reading["simulation_time"] == lineage["command"]["simulation_time"]
    assert reading["value"] > 28.0
    assert lineage["weather"]["simulation_time"] == lineage["command"]["simulation_time"]
    assert lineage["run"]["id"] == str(RUN_ID)
    assert lineage["run"]["random_seed"] == 42
    assert lineage["run"]["rule_set_version"].startswith("rules.v1:")

    missing = await api_client.get(f"/control-events/{uuid.uuid4()}/lineage")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_history_aggregates_and_quality_report(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    await api_client.post(f"/simulations/{RUN_ID}/start")
    await _step(api_client, 4)
    await _inject(api_client, sensor_type="temperature", fault_type="stuck")
    await _step(api_client, 6)

    sensors = (await api_client.get(f"/farms/{FARM_ID}/sensors")).json()
    temp_code = next(s["code"] for s in sensors if s["sensor_type"] == "temperature")
    raw = await api_client.get(
        f"/simulations/{RUN_ID}/readings/history",
        params={"bucket_seconds": 0, "sensor_code": temp_code},
    )
    assert raw.status_code == 200, raw.text
    raw_series = raw.json()["series"]
    assert len(raw_series) == 1
    raw_points = raw_series[0]["points"]
    assert [point["t"] for point in raw_points] == [60.0 * k for k in range(1, 11)]
    assert raw_points[-1]["quality"] == "bad"

    five_min = (
        await api_client.get(
            f"/farms/{FARM_ID}/readings/history",
            params={"bucket_seconds": 300, "sensor_code": temp_code},
        )
    ).json()
    buckets = five_min["series"][0]["points"]
    # 60..240 → 0 구간, 300..540 → 300 구간, 600 → 600 구간
    assert [point["t"] for point in buckets] == [0.0, 300.0, 600.0]
    assert [point["count"] for point in buckets] == [4, 5, 1]
    assert sum(sum(point["quality_counts"].values()) for point in buckets) == 10
    first = buckets[0]
    assert first["min"] <= first["avg"] <= first["max"]
    # good 이 없는 구간은 avg 가 비어 있다
    assert buckets[2]["quality_counts"]["bad"] == 1
    assert buckets[2]["avg"] is None

    all_sensors = (
        await api_client.get(f"/simulations/{RUN_ID}/readings/history", params={"bucket_seconds": 60})
    ).json()
    assert len(all_sensors["series"]) >= 5

    invalid = await api_client.get(
        f"/simulations/{RUN_ID}/readings/history", params={"bucket_seconds": 120}
    )
    assert invalid.status_code == 422

    report = (await api_client.get(f"/farms/{FARM_ID}/quality-report")).json()
    assert report["run_id"] == str(RUN_ID)
    temp = next(item for item in report["sensors"] if item["sensor_code"] == temp_code)
    assert temp["total"] == 10
    assert temp["quality_counts"]["bad"] >= 1
    assert temp["good_ratio"] < 1.0
    assert temp["faults"][0]["fault_type"] == "stuck"
    assert temp["faults"][0]["end_simulation_time"] is None
    assert any("flatline" in reason["reason"] for reason in temp["top_reasons"])
    assert report["total"] == sum(item["total"] for item in report["sensors"])
