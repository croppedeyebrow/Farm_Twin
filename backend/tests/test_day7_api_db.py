"""
2단계 Day 7 — migration 이후 API·제약 통합 테스트 (실 DB 필요).

seed 고정 UUID 로 /farms snapshot·state·readings 를 검증하고,
UNIQUE/CHECK 등 DB 제약이 살아 있는지 확인한다.
Windows 에서는 function-scoped event loop 와 풀이 섞이지 않게
fixture 에서 engine.dispose() 한다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.db.models import FarmState, SensorReading
from app.db.seed import FARM_ID, RUN_ID, seed_mvp
from app.db.session import SessionLocal, engine
from app.domain.enums import ReadingQuality, ReadingSource, Unit
from app.main import app

ROOM_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
SENSOR_TEMP_ID = uuid.UUID("66666666-6666-6666-6666-666666666661")


@pytest.fixture
async def seeded_farm(require_postgres: None) -> None:
    await seed_mvp(force=False)


@pytest.fixture
async def api_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_list_farms_contains_seed(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    response = await api_client.get("/farms")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert str(FARM_ID) in ids


@pytest.mark.asyncio
async def test_farm_snapshot(seeded_farm: None, api_client: AsyncClient) -> None:
    response = await api_client.get(f"/farms/{FARM_ID}/snapshot")
    assert response.status_code == 200
    body = response.json()
    assert body["farm"]["id"] == str(FARM_ID)
    assert body["state"]["version"] >= 1
    assert len(body["sensors"]) == 5
    assert len(body["actuators"]) == 5
    assert len(body["racks"]) == 3


@pytest.mark.asyncio
async def test_farm_state_endpoint(seeded_farm: None, api_client: AsyncClient) -> None:
    response = await api_client.get(f"/farms/{FARM_ID}/state")
    assert response.status_code == 200
    assert "temperature_c" in response.json()


@pytest.mark.asyncio
async def test_postgis_distance_query(seeded_farm: None) -> None:
    async with engine.connect() as connection:
        distance = await connection.scalar(
            text(
                """
                SELECT ST_Distance(
                    location,
                    ST_GeogFromText('SRID=4326;POINT(126.9880 37.5665)')
                )
                FROM sites
                WHERE id = CAST(:site_id AS uuid)
                """
            ),
            {"site_id": "11111111-1111-1111-1111-111111111111"},
        )
    assert distance is not None
    assert float(distance) > 0


@pytest.mark.asyncio
async def test_sensor_reading_sequence_unique(seeded_farm: None) -> None:
    now = datetime.now(UTC)
    unique_seq = int(uuid.uuid4().int % 1_000_000_000) + 2_000_000

    async with SessionLocal() as session:
        session.add(
            SensorReading(
                sensor_id=SENSOR_TEMP_ID,
                farm_id=FARM_ID,
                room_id=ROOM_ID,
                simulation_run_id=RUN_ID,
                sequence=unique_seq,
                value=24.1,
                raw_value=24.1,
                unit=Unit.CELSIUS,
                input_unit=Unit.CELSIUS,
                quality=ReadingQuality.GOOD,
                source=ReadingSource.SIMULATED,
                sensor_model_version="v1",
                simulation_time=100.0,
                sampled_at=now,
                ingested_at=now,
            )
        )
        await session.commit()

        session.add(
            SensorReading(
                sensor_id=SENSOR_TEMP_ID,
                farm_id=FARM_ID,
                room_id=ROOM_ID,
                simulation_run_id=RUN_ID,
                sequence=unique_seq,
                value=24.2,
                raw_value=24.2,
                unit=Unit.CELSIUS,
                input_unit=Unit.CELSIUS,
                quality=ReadingQuality.GOOD,
                source=ReadingSource.SIMULATED,
                sensor_model_version="v1",
                simulation_time=101.0,
                sampled_at=now,
                ingested_at=now,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_latest_readings_order_uses_simulation_time(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    now = datetime.now(UTC)
    base_seq = int(uuid.uuid4().int % 1_000_000_000) + 3_000_000

    async with SessionLocal() as session:
        for offset, sim_time, value in ((0, 1000.0, 25.0), (1, 1001.0, 26.0)):
            session.add(
                SensorReading(
                    sensor_id=SENSOR_TEMP_ID,
                    farm_id=FARM_ID,
                    room_id=ROOM_ID,
                    simulation_run_id=RUN_ID,
                    sequence=base_seq + offset,
                    value=value,
                    raw_value=value,
                    unit=Unit.CELSIUS,
                    input_unit=Unit.CELSIUS,
                    quality=ReadingQuality.GOOD,
                    source=ReadingSource.SIMULATED,
                    sensor_model_version="v1",
                    simulation_time=sim_time,
                    sampled_at=now,
                    ingested_at=now,
                )
            )
        await session.commit()

    response = await api_client.get(f"/sensors/{SENSOR_TEMP_ID}/readings?limit=2")
    assert response.status_code == 200
    body = response.json()
    assert body[0]["simulation_time"] >= body[1]["simulation_time"]


@pytest.mark.asyncio
async def test_farm_state_version_bump(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    async with SessionLocal() as session:
        state = await session.scalar(select(FarmState).where(FarmState.farm_id == FARM_ID))
        assert state is not None
        before = state.version
        state.version = before + 1
        state.temperature_c = state.temperature_c + 0.1
        await session.commit()
        after = before + 1

    response = await api_client.get(f"/farms/{FARM_ID}/state")
    assert response.json()["version"] == after
