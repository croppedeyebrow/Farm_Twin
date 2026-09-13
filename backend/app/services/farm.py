"""Farm 조회·스냅샷 서비스 (2단계 Day 7)."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Actuator, Farm, FarmState, Rack, Room, Sensor, SensorReading
from app.schemas.farm import (
    ActuatorSummary,
    FarmSnapshot,
    FarmStateOut,
    FarmSummary,
    RackSummary,
    RoomSummary,
    SensorReadingOut,
    SensorSummary,
)


async def list_farms(session: AsyncSession) -> list[FarmSummary]:
    result = await session.scalars(select(Farm).order_by(Farm.code))
    return [FarmSummary.model_validate(farm) for farm in result.all()]


async def get_farm_or_404(session: AsyncSession, farm_id: uuid.UUID) -> Farm:
    farm = await session.get(Farm, farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail="farm not found")
    return farm


async def get_farm_snapshot(session: AsyncSession, farm_id: uuid.UUID) -> FarmSnapshot:
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
    state = await session.scalar(select(FarmState).where(FarmState.room_id == room.id))

    return FarmSnapshot(
        farm=FarmSummary.model_validate(farm),
        room=RoomSummary.model_validate(room),
        racks=[RackSummary.model_validate(rack) for rack in racks],
        sensors=[SensorSummary.model_validate(sensor) for sensor in sensors],
        actuators=[ActuatorSummary.model_validate(actuator) for actuator in actuators],
        state=FarmStateOut.model_validate(state) if state else None,
    )


async def get_farm_state(session: AsyncSession, farm_id: uuid.UUID) -> FarmStateOut:
    await get_farm_or_404(session, farm_id)
    state = await session.scalar(select(FarmState).where(FarmState.farm_id == farm_id))
    if state is None:
        raise HTTPException(status_code=404, detail="farm state not found")
    return FarmStateOut.model_validate(state)


async def list_farm_sensors(
    session: AsyncSession,
    farm_id: uuid.UUID,
) -> list[SensorSummary]:
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
