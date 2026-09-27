"""
수동 설비 변경의 명령·이벤트 기록 (6단계 Day 23).

수동 출력도 ControlCommand(rule_id=null) + ControlEvent 로 남긴다.
- lineage: 설비 상태 변화마다 원인이 규칙인지 운영자인지 추적된다
- replay : 원본 run 의 수동 변경을 같은 가상 시각에 다시 적용할 수 있다

기록 대상 run 은 그 룸에서 진행 중(RUNNING/PAUSED)인 최신 run.
진행 중 run 이 없으면 설비 캐시만 바뀌고 이력은 남지 않는다 (run 없는 명령은 없다).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Actuator, ControlCommand, ControlEvent, SimulationRun
from app.domain.enums import (
    ActuatorMode,
    ControlCommandStatus,
    ControlEventType,
    SimulationStatus,
)
from app.services.room_control import IDEMPOTENCY_KEY_MAX_LENGTH

MANUAL_REASON = "manual"


async def active_run_for_room(
    session: AsyncSession,
    room_id: uuid.UUID,
) -> SimulationRun | None:
    return await session.scalar(
        select(SimulationRun)
        .where(
            SimulationRun.room_id == room_id,
            SimulationRun.status.in_([SimulationStatus.RUNNING, SimulationStatus.PAUSED]),
        )
        .order_by(SimulationRun.created_at.desc())
        .limit(1)
    )


def record_manual_command(
    session: AsyncSession,
    run: SimulationRun,
    actuator: Actuator,
    *,
    simulation_time: float,
    now: datetime,
) -> ControlCommand:
    """설비에 이미 반영된 수동 출력(mode/output_ratio)을 명령·이벤트로 남긴다."""
    active = actuator.mode is not ActuatorMode.OFF
    command = ControlCommand(
        id=uuid.uuid4(),
        simulation_run_id=run.id,
        actuator_id=actuator.id,
        rule_id=None,
        idempotency_key=(
            f"{run.id}:manual:{actuator.code}:{uuid.uuid4().hex[:12]}@{simulation_time:.3f}"
        )[:IDEMPOTENCY_KEY_MAX_LENGTH],
        status=ControlCommandStatus.SUCCEEDED,
        desired_mode=actuator.mode,
        desired_output_ratio=actuator.output_ratio,
        simulation_time=simulation_time,
        issued_at=now,
        reason=MANUAL_REASON,
    )
    session.add(command)
    session.add(
        ControlEvent(
            command_id=command.id,
            simulation_run_id=run.id,
            event_type=ControlEventType.APPLIED if active else ControlEventType.STOPPED,
            actual_output_ratio=actuator.output_ratio,
            message=(
                f"수동 제어: {actuator.name} {actuator.output_ratio * 100:.0f}%"
                if active
                else f"수동 제어: {actuator.name} 끔"
            ),
            simulation_time=simulation_time,
            recorded_at=now,
        )
    )
    return command
