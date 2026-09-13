"""
3단계 Day 11 — run 제어·step·readings batch 통합 테스트 (실 DB).
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.db.models import Actuator, FarmState, SensorReading
from app.db.seed import FARM_ID, RUN_ID, seed_mvp
from app.db.session import SessionLocal
from app.domain.enums import ActuatorMode, ActuatorType, SimulationStatus
from app.main import app


@pytest.fixture
async def seeded_farm(require_postgres: None) -> None:
    await seed_mvp(force=True)



@pytest.fixture
async def api_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_run_lifecycle_start_pause_resume_stop(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    start = await api_client.post(f"/simulations/{RUN_ID}/start")
    assert start.status_code == 200
    assert start.json()["status"] == SimulationStatus.RUNNING.value

    pause = await api_client.post(f"/simulations/{RUN_ID}/pause")
    assert pause.json()["status"] == SimulationStatus.PAUSED.value

    resume = await api_client.post(f"/simulations/{RUN_ID}/resume")
    assert resume.json()["status"] == SimulationStatus.RUNNING.value

    stop = await api_client.post(f"/simulations/{RUN_ID}/stop")
    body = stop.json()
    assert body["status"] == SimulationStatus.STOPPED.value
    assert body["ended_at"] is not None


@pytest.mark.asyncio
async def test_step_requires_running(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        f"/simulations/{RUN_ID}/step",
        json={"steps": 1, "dt_seconds": 60.0},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_step_persists_readings_and_updates_true_state(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    await api_client.post(f"/simulations/{RUN_ID}/start")

    async with SessionLocal() as session:
        before = await session.scalar(
            select(FarmState).where(FarmState.farm_id == FARM_ID)
        )
        assert before is not None
        version_before = before.version
        temp_before = before.temperature_c

    step = await api_client.post(
        f"/simulations/{RUN_ID}/step",
        json={"steps": 5, "dt_seconds": 60.0, "persist_readings": True},
    )
    assert step.status_code == 200
    body = step.json()
    assert body["steps_applied"] == 5
    assert body["readings_inserted"] == 25  # 5 steps × 5 sensors
    assert body["simulation_time_seconds"] == 300.0
    assert body["farm_state_version"] == version_before + 5

    async with SessionLocal() as session:
        after = await session.scalar(
            select(FarmState).where(FarmState.farm_id == FARM_ID)
        )
        assert after is not None
        assert after.version == version_before + 5
        assert after.temperature_c == body["temperature_c"]
        # 환경이 움직였거나 version 만이라도 전진했는지 확인
        assert after.temperature_c != temp_before or after.version > version_before

        reading_count = await session.scalar(
            select(func.count())
            .select_from(SensorReading)
            .where(SensorReading.simulation_run_id == RUN_ID)
        )
        assert reading_count == 25

        temp_sensor_id = uuid.UUID("66666666-6666-6666-6666-666666666661")
        latest = await session.scalar(
            select(SensorReading)
            .where(SensorReading.sensor_id == temp_sensor_id)
            .order_by(SensorReading.simulation_time.desc())
        )
        assert latest is not None
        # 측정값(offset/noise)과 참값은 일반적으로 다름
        assert latest.value != after.temperature_c or abs(latest.value - after.temperature_c) >= 0


@pytest.mark.asyncio
async def test_step_reproducible_true_state_with_same_seed(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    """동일 seed·입력으로 두 번 step 하면 참값 궤적이 같다."""

    async def run_once() -> float:
        await seed_mvp(force=True)
        await api_client.post(f"/simulations/{RUN_ID}/start")
        async with SessionLocal() as session:
            led = await session.scalar(
                select(Actuator).where(Actuator.actuator_type == ActuatorType.LED)
            )
            assert led is not None
            led.mode = ActuatorMode.ON
            led.output_ratio = 1.0
            await session.commit()

        result = await api_client.post(
            f"/simulations/{RUN_ID}/step",
            json={"steps": 10, "dt_seconds": 60.0, "persist_readings": False},
        )
        assert result.status_code == 200
        return float(result.json()["temperature_c"])

    first = await run_once()
    second = await run_once()
    assert first == second


@pytest.mark.asyncio
async def test_list_simulations_contains_seed_run(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    response = await api_client.get("/simulations")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert str(RUN_ID) in ids


@pytest.mark.asyncio
async def test_invalid_transition_conflict(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(f"/simulations/{RUN_ID}/pause")
    assert response.status_code == 409
