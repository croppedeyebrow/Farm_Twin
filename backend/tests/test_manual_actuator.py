"""트윈 대시보드 — 수동 액추에이터 설정."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.seed import FARM_ID, seed_mvp
from app.domain.enums import ActuatorMode, ActuatorType
from app.main import app


@pytest.fixture
async def seeded_farm(require_postgres: None) -> None:
    await seed_mvp(force=False)


@pytest.fixture
async def api_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_manual_led_set_updates_mode_and_ratio(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    actuators = await api_client.get(f"/farms/{FARM_ID}/actuators")
    assert actuators.status_code == 200
    led = next(
        item
        for item in actuators.json()
        if item["actuator_type"] == ActuatorType.LED.value
    )

    response = await api_client.post(
        f"/actuators/{led['id']}/manual",
        json={"output_ratio": 0.65},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == ActuatorMode.MANUAL.value
    assert body["output_ratio"] == pytest.approx(0.65)

    off = await api_client.post(
        f"/actuators/{led['id']}/manual",
        json={"output_ratio": 0.0},
    )
    assert off.status_code == 200
    assert off.json()["mode"] == ActuatorMode.OFF.value
    assert off.json()["output_ratio"] == 0.0


@pytest.mark.asyncio
async def test_manual_rejects_out_of_range(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    fake_id = uuid.uuid4()
    response = await api_client.post(
        f"/actuators/{fake_id}/manual",
        json={"output_ratio": 1.5},
    )
    assert response.status_code == 422
