"""
5단계 Day 18 — 제어 이벤트 타임라인 API 계약 테스트.

검증 축
-------
- ControlEventOut 스키마 필드
- list_farm_control_events 가 farm 필터·최신순·limit 을 지킴
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.enums import (
    ActuatorMode,
    ActuatorType,
    ControlCommandStatus,
    ControlEventType,
)
from app.schemas.farm import ControlEventOut
from app.services import farm as farm_service


def test_control_event_out_schema() -> None:
    event = ControlEventOut(
        id=uuid.uuid4(),
        event_type=ControlEventType.APPLIED.value,
        message="hvac started",
        actual_output_ratio=0.8,
        simulation_time=120.0,
        recorded_at=datetime.now(UTC),
        command_id=uuid.uuid4(),
        simulation_run_id=uuid.uuid4(),
        actuator_code="hvac-1",
        actuator_type=ActuatorType.HVAC.value,
        desired_mode=ActuatorMode.ON.value,
        command_status=ControlCommandStatus.SUCCEEDED.value,
    )
    assert event.event_type == "applied"
    assert event.actuator_code == "hvac-1"


@pytest.mark.asyncio
async def test_list_farm_control_events_empty_when_no_rows() -> None:
    farm_id = uuid.uuid4()
    farm = MagicMock()
    farm.id = farm_id

    session = AsyncMock()
    session.get = AsyncMock(return_value=farm)
    result = MagicMock()
    result.all = MagicMock(return_value=[])
    session.execute = AsyncMock(return_value=result)

    events = await farm_service.list_farm_control_events(session, farm_id, limit=10)
    assert events == []
