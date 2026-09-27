"""
6단계 Day 22 — 센서 고장 주입, 고장 이력, 규칙 엔진의 bad 측정 정책.

검증 의도
---------
- spike/stuck/dropout 은 측정에만 적용되고 참값(FarmState)은 그대로다
- 품질 판정이 고장을 잡는다: spike→suspect, stuck→bad(flatline), dropout→stale→복구 시 missing
- 고장 시작·해제가 fault_injections 에 남는다
- 규칙은 측정값·품질로 판정한다: suspect 는 보류, bad 는 차단, 차단 구간 시작만 기록
- 정상 측정이면 냉방 START/STOP 사이클이 반복돼도 명령 키가 충돌하지 않는다
- MANUAL 설비는 규칙이 건드리지 않는다
"""

from __future__ import annotations

import math

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import (
    Actuator,
    ControlCommand,
    ControlEvent,
    FarmState,
    FaultInjection,
    Sensor,
    SensorReading,
)
from app.db.seed import FARM_ID, ROOM_ID, RUN_ID, seed_mvp
from app.db.session import SessionLocal
from app.domain.enums import (
    ActuatorMode,
    ActuatorType,
    ControlCommandStatus,
    ControlEventType,
    FaultType,
    ReadingQuality,
    SensorType,
)
from app.domain.simulation.faults import ActiveFault, apply_fault, spike_active_at
from app.domain.simulation.sensors import VirtualSensorBank
from app.domain.simulation.state import EnvironmentState
from app.domain.telemetry import QualityReason, StreamQualityAssessor
from app.main import app
from app.services.room_control import clear_blocked_cache
from app.services.sender import SENDER_SEQUENCES, SenderSequences

# ---------------------------------------------------------------------------
# 고장 적용 (도메인)
# ---------------------------------------------------------------------------


def _fault(fault_type: FaultType, **kwargs: float) -> ActiveFault:
    return ActiveFault(
        sensor_type=SensorType.TEMPERATURE,
        fault_type=fault_type,
        start_simulation_time=600.0,
        **kwargs,
    )


def test_fault_not_applied_before_start_or_without_fault() -> None:
    assert apply_fault(24.0, None, simulation_time=900.0) == 24.0
    assert apply_fault(24.0, _fault(FaultType.DROPOUT), simulation_time=540.0) == 24.0


def test_dropout_and_stuck() -> None:
    assert apply_fault(24.0, _fault(FaultType.DROPOUT), simulation_time=660.0) is None
    stuck = _fault(FaultType.STUCK, stuck_value=21.5)
    assert apply_fault(24.3, stuck, simulation_time=660.0) == 21.5
    assert apply_fault(26.0, stuck, simulation_time=720.0) == 21.5


def test_spike_alternates_from_first_sample() -> None:
    spike = _fault(FaultType.SPIKE, magnitude=8.0)
    assert [spike_active_at(spike, 600.0 + 60.0 * k) for k in range(1, 5)] == [
        True,
        False,
        True,
        False,
    ]
    assert apply_fault(24.0, spike, simulation_time=660.0) == 32.0
    assert apply_fault(24.0, spike, simulation_time=720.0) == 24.0
    # magnitude 가 없으면 센서 타입 기본값
    assert apply_fault(24.0, _fault(FaultType.SPIKE), simulation_time=660.0) == 32.0


def test_sensor_bank_applies_faults_without_touching_state() -> None:
    state = EnvironmentState(
        temperature_c=24.0,
        humidity_pct=60.0,
        co2_ppm=800.0,
        substrate_moisture_pct=45.0,
        ppfd_umol=0.0,
        simulation_time=660.0,
    )
    faults = {
        SensorType.TEMPERATURE: _fault(FaultType.STUCK, stuck_value=21.5),
        SensorType.HUMIDITY: ActiveFault(
            sensor_type=SensorType.HUMIDITY,
            fault_type=FaultType.DROPOUT,
            start_simulation_time=600.0,
        ),
    }
    samples = VirtualSensorBank(seed=42).measure(state, faults=faults)
    by_type = {sample.sensor_type: sample for sample in samples}

    assert SensorType.HUMIDITY not in by_type
    assert by_type[SensorType.TEMPERATURE].raw_value == 21.5
    assert by_type[SensorType.TEMPERATURE].true_value == 24.0
    assert state.temperature_c == 24.0


# ---------------------------------------------------------------------------
# stuck 검출 (flatline) · 송신 sequence
# ---------------------------------------------------------------------------


def test_flatline_marks_repeated_raw_as_bad() -> None:
    assessor = StreamQualityAssessor()
    qualities = []
    for k in range(6):
        result = assessor.assess(
            "s",
            sensor_type=SensorType.TEMPERATURE,
            source_sequence=k,
            value=21.5,
            raw_value=21.5,
            simulation_time=60.0 * k,
        )
        assert result.verdict is not None
        qualities.append(result.verdict.quality)
    assert qualities == [ReadingQuality.GOOD] * 3 + [ReadingQuality.BAD] * 3
    assert QualityReason.FLATLINE.value in result.verdict.reasons

    # 값이 다시 움직이면 연속이 끊긴다
    recovered = assessor.assess(
        "s",
        sensor_type=SensorType.TEMPERATURE,
        source_sequence=6,
        value=21.6,
        raw_value=21.6,
        simulation_time=360.0,
    )
    assert recovered.verdict is not None
    assert recovered.verdict.quality is ReadingQuality.GOOD


def test_flatline_ignores_ppfd_night_zeros() -> None:
    assessor = StreamQualityAssessor()
    for k in range(6):
        result = assessor.assess(
            "p",
            sensor_type=SensorType.PPFD,
            source_sequence=k,
            value=0.0,
            raw_value=0.0,
            simulation_time=60.0 * k,
        )
        assert result.verdict is not None
        assert result.verdict.quality is ReadingQuality.GOOD


def test_sender_sequence_skips_dropped_numbers_until_recovery() -> None:
    sender = SenderSequences()
    assessor = StreamQualityAssessor()
    run_id = RUN_ID
    sensor_id = RUN_ID

    def deliver(t: float) -> int:
        seq = sender.issue(run_id, sensor_id, assessor)
        assessor.assess(
            sensor_id,
            sensor_type=SensorType.TEMPERATURE,
            source_sequence=seq,
            value=24.0 + t / 1000,
            simulation_time=t,
        )
        sender.delivered(run_id, sensor_id, seq)
        return seq

    assert deliver(60.0) == 0
    assert sender.issue(run_id, sensor_id, assessor) == 1  # dropout
    assert sender.issue(run_id, sensor_id, assessor) == 2  # dropout
    assert deliver(240.0) == 3

    # 수신측 상태가 커서와 다르면(재시드 등) 수신측 기준으로 돌아간다
    fresh = StreamQualityAssessor()
    assert sender.issue(run_id, sensor_id, fresh) == 0


# ---------------------------------------------------------------------------
# 통합 (실 DB)
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


async def _step(client: AsyncClient, steps: int = 1) -> dict:
    response = await client.post(
        f"/simulations/{RUN_ID}/step",
        json={"steps": steps, "dt_seconds": 60.0},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _inject(client: AsyncClient, **body: object) -> dict:
    response = await client.post(f"/simulations/{RUN_ID}/faults", json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def _rows(sensor_type: SensorType) -> list[SensorReading]:
    async with SessionLocal() as session:
        sensor = await session.scalar(
            select(Sensor).where(Sensor.room_id == ROOM_ID, Sensor.sensor_type == sensor_type)
        )
        assert sensor is not None
        return list(
            (
                await session.scalars(
                    select(SensorReading)
                    .where(SensorReading.sensor_id == sensor.id)
                    .order_by(SensorReading.sequence)
                )
            ).all()
        )


async def _set_true_temperature(value: float) -> None:
    async with SessionLocal() as session:
        state = await session.scalar(select(FarmState).where(FarmState.room_id == ROOM_ID))
        assert state is not None
        state.temperature_c = value
        await session.commit()


async def _hvac() -> Actuator:
    async with SessionLocal() as session:
        hvac = await session.scalar(
            select(Actuator).where(
                Actuator.room_id == ROOM_ID,
                Actuator.actuator_type == ActuatorType.HVAC,
            )
        )
        assert hvac is not None
        return hvac


async def _events() -> list[tuple[ControlCommand, ControlEvent]]:
    async with SessionLocal() as session:
        rows = await session.execute(
            select(ControlCommand, ControlEvent)
            .join(ControlEvent, ControlEvent.command_id == ControlCommand.id)
            .where(ControlCommand.simulation_run_id == RUN_ID)
            .order_by(ControlEvent.simulation_time)
        )
        return list(rows.tuples().all())


@pytest.mark.asyncio
async def test_inject_and_clear_fault_records_history(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    await api_client.post(f"/simulations/{RUN_ID}/start")
    await _step(api_client, 2)

    fault = await _inject(api_client, sensor_type="temperature", fault_type="spike")
    assert fault["active"] is True
    assert fault["magnitude"] == 8.0
    assert fault["start_simulation_time"] == 120.0

    duplicate = await api_client.post(
        f"/simulations/{RUN_ID}/faults",
        json={"sensor_type": "temperature", "fault_type": "dropout"},
    )
    assert duplicate.status_code == 409

    zone_sensor = await api_client.post(
        f"/simulations/{RUN_ID}/faults",
        json={"sensor_type": "substrate_ec", "fault_type": "spike"},
    )
    assert zone_sensor.status_code == 422

    await _step(api_client, 2)
    cleared = await api_client.post(
        f"/simulations/{RUN_ID}/faults/{fault['id']}/clear",
        json={"reason": "센서 교체"},
    )
    assert cleared.status_code == 200
    body = cleared.json()
    assert body["active"] is False
    assert body["end_simulation_time"] == 240.0
    assert body["notes"] == "cleared: 센서 교체"

    again = await api_client.post(f"/simulations/{RUN_ID}/faults/{fault['id']}/clear")
    assert again.status_code == 409

    listing = await api_client.get(f"/farms/{FARM_ID}/faults")
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()["faults"]] == [fault["id"]]


@pytest.mark.asyncio
async def test_spike_is_suspect_and_raw_preserved(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    await api_client.post(f"/simulations/{RUN_ID}/start")
    await _step(api_client, 1)
    await _inject(api_client, sensor_type="temperature", fault_type="spike")
    result = await _step(api_client, 2)

    # 참값은 고장과 무관
    assert abs(result["temperature_c"] - 24.0) < 2.0

    rows = await _rows(SensorType.TEMPERATURE)
    spiked, back = rows[1], rows[2]
    assert spiked.raw_value - back.raw_value > 6.0
    assert spiked.quality is ReadingQuality.SUSPECT
    assert QualityReason.RATE_OF_CHANGE.value in (spiked.quality_reason or "")
    assert back.quality is ReadingQuality.SUSPECT

    health = (await api_client.get(f"/farms/{FARM_ID}/sensors/health")).json()
    temp = next(s for s in health["sensors"] if s["sensor_type"] == "temperature")
    assert temp["quality"] == "suspect"


@pytest.mark.asyncio
async def test_stuck_is_detected_as_bad_flatline(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    await api_client.post(f"/simulations/{RUN_ID}/start")
    await _step(api_client, 1)
    fault = await _inject(api_client, sensor_type="temperature", fault_type="stuck")
    # 기본 stuck 값은 주입 시점 최신 측정값
    rows = await _rows(SensorType.TEMPERATURE)
    assert fault["stuck_value"] == pytest.approx(rows[-1].value)

    # HTTP 호출을 나눠도 연속 횟수가 DB 에서 이어진다
    for _ in range(4):
        await _step(api_client, 1)

    rows = await _rows(SensorType.TEMPERATURE)
    stuck_rows = rows[1:]
    assert all(row.raw_value == fault["stuck_value"] for row in stuck_rows)
    # 주입 전 마지막 값 + 고정 3개 = 4 연속부터 BAD
    assert [row.quality for row in stuck_rows] == [
        ReadingQuality.GOOD,
        ReadingQuality.GOOD,
        ReadingQuality.BAD,
        ReadingQuality.BAD,
    ]
    assert stuck_rows[-1].quality_reason == QualityReason.FLATLINE.value


@pytest.mark.asyncio
async def test_dropout_goes_stale_then_marks_gap_on_recovery(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    await api_client.post(f"/simulations/{RUN_ID}/start")
    await _step(api_client, 1)
    fault = await _inject(api_client, sensor_type="temperature", fault_type="dropout")
    await _step(api_client, 2)
    await _step(api_client, 2)

    rows = await _rows(SensorType.TEMPERATURE)
    assert len(rows) == 1

    health = (await api_client.get(f"/farms/{FARM_ID}/sensors/health")).json()
    temp = next(s for s in health["sensors"] if s["sensor_type"] == "temperature")
    assert temp["quality"] == "stale"
    assert temp["quality_reason"] == QualityReason.STALE_SIMULATION.value

    await api_client.post(f"/simulations/{RUN_ID}/faults/{fault['id']}/clear")
    await _step(api_client, 1)

    rows = await _rows(SensorType.TEMPERATURE)
    assert [row.source_sequence for row in rows] == [0, 1, 2, 3, 4, 5]
    assert [row.quality for row in rows[1:5]] == [ReadingQuality.MISSING] * 4
    assert QualityReason.SEQUENCE_GAP.value in (rows[-1].quality_reason or "")

    # 고장 중에도 다른 센서는 계속 측정된다
    assert len(await _rows(SensorType.HUMIDITY)) == 6


@pytest.mark.asyncio
async def test_good_high_temperature_cycles_hvac(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    await _set_true_temperature(31.0)
    await api_client.post(f"/simulations/{RUN_ID}/start")
    first = await _step(api_client, 1)
    assert first["commands_issued"] == 1
    hvac = await _hvac()
    assert hvac.mode is ActuatorMode.ON
    assert hvac.output_ratio == pytest.approx(0.8)

    # 저온 → (변화율 suspect 로 한 스텝 보류) → STOP
    await _set_true_temperature(20.0)
    await _step(api_client, 2)
    assert (await _hvac()).mode is ActuatorMode.OFF

    # 두 번째 사이클 START — 명령 키가 시각으로 구분돼 UNIQUE 충돌이 없다
    await _set_true_temperature(31.0)
    await _step(api_client, 2)
    assert (await _hvac()).mode is ActuatorMode.ON

    succeeded = [
        (command, event)
        for command, event in await _events()
        if command.status is ControlCommandStatus.SUCCEEDED
    ]
    assert [event.event_type for _, event in succeeded] == [
        ControlEventType.APPLIED,
        ControlEventType.STOPPED,
        ControlEventType.APPLIED,
    ]
    assert len({command.idempotency_key for command, _ in succeeded}) == 3


@pytest.mark.asyncio
async def test_spike_does_not_start_hvac_and_logs_block_once(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    await api_client.post(f"/simulations/{RUN_ID}/start")
    await _step(api_client, 1)
    await _inject(api_client, sensor_type="temperature", fault_type="spike")

    result = await _step(api_client, 4)
    # 튄 값(≈32℃)은 임계 28℃ 를 넘지만 suspect 라 보류 — 냉방 미가동
    assert result["commands_issued"] == 0
    assert result["control_blocked"] == 1
    hvac = await _hvac()
    assert hvac.mode is ActuatorMode.OFF

    events = await _events()
    assert len(events) == 1
    command, event = events[0]
    assert command.status is ControlCommandStatus.CANCELLED
    assert event.event_type is ControlEventType.REJECTED
    assert "suspect" in (event.message or "")

    timeline = (await api_client.get(f"/farms/{FARM_ID}/events")).json()
    assert timeline[0]["event_type"] == "rejected"


@pytest.mark.asyncio
async def test_bad_stuck_reading_blocks_rule(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    await _set_true_temperature(31.0)
    await api_client.post(f"/simulations/{RUN_ID}/start")
    await _step(api_client, 1)
    assert (await _hvac()).mode is ActuatorMode.ON

    # 냉방 중 센서가 고온에 고정 → 실제 온도가 내려가도 STOP 판단을 못 한다.
    # flatline 검출 뒤에는 규칙이 bad 로 차단되고 설비는 그대로 유지된다.
    await _inject(api_client, sensor_type="temperature", fault_type="stuck", stuck_value=31.0)
    await _set_true_temperature(20.0)
    result = await _step(api_client, 4)

    blocked = [
        event
        for command, event in await _events()
        if command.status is ControlCommandStatus.CANCELLED
    ]
    assert result["control_blocked"] == 1
    assert "bad" in (blocked[-1].message or "")
    assert (await _hvac()).mode is ActuatorMode.ON


@pytest.mark.asyncio
async def test_manual_actuator_is_not_overridden(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    hvac = await _hvac()
    manual = await api_client.post(
        f"/actuators/{hvac.id}/manual", json={"output_ratio": 0.3}
    )
    assert manual.status_code == 200

    await _set_true_temperature(20.0)
    await api_client.post(f"/simulations/{RUN_ID}/start")
    result = await _step(api_client, 2)

    assert result["commands_issued"] == 0
    after = await _hvac()
    assert after.mode is ActuatorMode.MANUAL
    assert after.output_ratio == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_fault_stays_open_until_cleared(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    await api_client.post(f"/simulations/{RUN_ID}/start")
    await _inject(api_client, sensor_type="humidity", fault_type="dropout")
    async with SessionLocal() as session:
        faults = (await session.scalars(select(FaultInjection))).all()
    assert len(faults) == 1
    assert faults[0].end_simulation_time is None
    assert not math.isnan(faults[0].start_simulation_time)
