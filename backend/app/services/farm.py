"""
Farm 조회·스냅샷·이벤트 애플리케이션 서비스
(2단계 Day 7, 5단계 Day 17~18).

계층
----
routers → **services** → ORM/SQLAlchemy → PostgreSQL
                    └→ ConnectionManager.last_sequence (Day 17 stream 정렬)

라우터는 HTTP 만 담당하고, 조회 조합·404 정책은 여기에 둔다.
시뮬레이터(3단계+)도 같은 세션/모델 계약을 재사용할 수 있다.

Day 17
------
snapshot 에 stream_sequence 를 실어
  초기 로딩 / 재연결 / sequence 갭 복구
시 클라이언트가 REST 한 번으로 상태+스트림 기준을 맞추게 한다.

Day 18
------
list_farm_control_events: 관제 타임라인용 ControlEvent 이력.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Actuator, Farm, FarmState, Rack, Room, Sensor, SensorReading
from app.db.models.control import ControlCommand, ControlEvent
from app.db.models.simulation import SimulationRun
from app.schemas.farm import (
    ActuatorSummary,
    ControlEventOut,
    FarmSnapshot,
    FarmStateOut,
    FarmSummary,
    RackSummary,
    RoomSummary,
    SensorReadingOut,
    SensorSummary,
)
from app.websocket.manager import get_connection_manager


async def list_farms(session: AsyncSession) -> list[FarmSummary]:
    """등록된 농장 목록 (code 정렬)."""
    result = await session.scalars(select(Farm).order_by(Farm.code))
    return [FarmSummary.model_validate(farm) for farm in result.all()]


async def get_farm_or_404(session: AsyncSession, farm_id: uuid.UUID) -> Farm:
    """없으면 404. 서비스 내부 공통 가드."""
    farm = await session.get(Farm, farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail="farm not found")
    return farm


async def get_farm_snapshot(session: AsyncSession, farm_id: uuid.UUID) -> FarmSnapshot:
    """
    관제 초기·복구용 통합 스냅샷.

    MVP 는 farm 당 room 1개를 가정한다 (seed 기준).
    이후 다룸이면 room_id 쿼리 파라미터가 필요하다.

    stream_sequence 는 DB 가 아니라 이 프로세스 ConnectionManager 기준이다.
    WS 가 아직 한 번도 publish 하지 않았으면 0.
    """
    farm = await get_farm_or_404(session, farm_id)
    room = await session.scalar(select(Room).where(Room.farm_id == farm_id).limit(1))
    if room is None:
        raise HTTPException(status_code=404, detail="room not found for farm")

    racks = (
        await session.scalars(
            select(Rack).where(Rack.room_id == room.id).order_by(Rack.code)
        )
    ).all()
    sensors = (
        await session.scalars(
            select(Sensor).where(Sensor.room_id == room.id).order_by(Sensor.code)
        )
    ).all()
    actuators = (
        await session.scalars(
            select(Actuator).where(Actuator.room_id == room.id).order_by(Actuator.code)
        )
    ).all()
    # room 당 최신 참값 1행
    state = await session.scalar(select(FarmState).where(FarmState.room_id == room.id))

    # Day 17: 관제 스트림 정렬 기준 (commit-then-push 로 발급된 마지막 번호)
    stream_sequence = get_connection_manager().last_sequence(farm_id)

    return FarmSnapshot(
        farm=FarmSummary.model_validate(farm),
        room=RoomSummary.model_validate(room),
        racks=[RackSummary.model_validate(rack) for rack in racks],
        sensors=[SensorSummary.model_validate(sensor) for sensor in sensors],
        actuators=[ActuatorSummary.model_validate(actuator) for actuator in actuators],
        state=FarmStateOut.model_validate(state) if state else None,
        stream_sequence=stream_sequence,
    )


async def get_farm_state(session: AsyncSession, farm_id: uuid.UUID) -> FarmStateOut:
    """환경 참값만 조회. 측정값(readings)과 혼동하지 않는다."""
    await get_farm_or_404(session, farm_id)
    state = await session.scalar(select(FarmState).where(FarmState.farm_id == farm_id))
    if state is None:
        raise HTTPException(status_code=404, detail="farm state not found")
    return FarmStateOut.model_validate(state)


async def list_farm_sensors(
    session: AsyncSession,
    farm_id: uuid.UUID,
) -> list[SensorSummary]:
    """farm 소속 모든 room 의 센서 메타데이터."""
    await get_farm_or_404(session, farm_id)
    rooms = (
        await session.scalars(select(Room.id).where(Room.farm_id == farm_id))
    ).all()
    if not rooms:
        return []
    sensors = (
        await session.scalars(
            select(Sensor).where(Sensor.room_id.in_(rooms)).order_by(Sensor.code)
        )
    ).all()
    return [SensorSummary.model_validate(sensor) for sensor in sensors]


async def list_sensor_readings(
    session: AsyncSession,
    sensor_id: uuid.UUID,
    *,
    limit: int = 100,
) -> list[SensorReadingOut]:
    """
    센서 시계열 (최신 simulation_time 우선).

    인덱스: ix_sensor_readings_sensor_id_simulation_time
    """
    sensor = await session.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found")

    readings = (
        await session.scalars(
            select(SensorReading)
            .where(SensorReading.sensor_id == sensor_id)
            .order_by(SensorReading.simulation_time.desc())
            .limit(limit)
        )
    ).all()
    return [SensorReadingOut.model_validate(item) for item in readings]


async def list_farm_actuators(
    session: AsyncSession,
    farm_id: uuid.UUID,
) -> list[ActuatorSummary]:
    """farm 소속 액추에이터 현재 mode/output 캐시 포함."""
    await get_farm_or_404(session, farm_id)
    room_ids = (
        await session.scalars(select(Room.id).where(Room.farm_id == farm_id))
    ).all()
    actuators = (
        await session.scalars(
            select(Actuator)
            .where(Actuator.room_id.in_(room_ids))
            .order_by(Actuator.code)
        )
    ).all()
    return [ActuatorSummary.model_validate(item) for item in actuators]


async def list_farm_control_events(
    session: AsyncSession,
    farm_id: uuid.UUID,
    *,
    limit: int = 50,
) -> list[ControlEventOut]:
    """
    농장 제어 이벤트 타임라인 (5단계 Day 18).

    ControlEvent ← Command ← Actuator, SimulationRun.farm_id 로 필터.
    최신 recorded_at 우선. 시드에 이벤트가 없으면 빈 목록 (정상).
    """
    await get_farm_or_404(session, farm_id)
    rows = (
        await session.execute(
            select(ControlEvent, ControlCommand, Actuator)
            .join(ControlCommand, ControlEvent.command_id == ControlCommand.id)
            .join(Actuator, ControlCommand.actuator_id == Actuator.id)
            .join(SimulationRun, ControlEvent.simulation_run_id == SimulationRun.id)
            .where(SimulationRun.farm_id == farm_id)
            .order_by(ControlEvent.recorded_at.desc())
            .limit(limit)
        )
    ).all()

    out: list[ControlEventOut] = []
    for event, command, actuator in rows:
        out.append(
            ControlEventOut(
                id=event.id,
                event_type=event.event_type.value,
                message=event.message,
                actual_output_ratio=event.actual_output_ratio,
                simulation_time=event.simulation_time,
                recorded_at=event.recorded_at,
                command_id=event.command_id,
                simulation_run_id=event.simulation_run_id,
                actuator_code=actuator.code,
                actuator_type=actuator.actuator_type.value,
                desired_mode=command.desired_mode.value,
                command_status=command.status.value,
            )
        )
    return out
