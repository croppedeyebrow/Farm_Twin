"""
센서 고장 주입 서비스 (6단계 Day 22).

=============================================================================
흐름
-----------------------------------------------------------------------------
  주입 : fault_injections 행 추가 (active, start_simulation_time = run 시계)
  적용 : step_run 이 활성 고장을 읽어 VirtualSensorBank.measure 에 넘긴다
  해제 : active=False + end_simulation_time / cleared_at 기록

원시 sensor_readings 는 건드리지 않는다. 고장 구간의 측정은 이미
고장이 적용된 raw 로 저장되고, 품질 판정이 이를 suspect/bad/stale 로 잡는다.

센서당 진행 중 고장은 하나만 둔다 (겹치면 효과 해석이 모호해진다).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    FarmState,
    FaultInjection,
    Sensor,
    SensorReading,
    SimulationRun,
)
from app.domain.enums import FaultType, SensorType, SimulationStatus
from app.domain.simulation.faults import DEFAULT_SPIKE_MAGNITUDE, ActiveFault
from app.domain.simulation.sensors import DEFAULT_SENSOR_CHANNELS, true_value_for
from app.schemas.fault import (
    FaultClearRequest,
    FaultInjectRequest,
    FaultListOut,
    FaultOut,
)

SIMULATED_SENSOR_TYPES: frozenset[SensorType] = frozenset(
    channel.sensor_type for channel in DEFAULT_SENSOR_CHANNELS
)
FAULT_HISTORY_LIMIT = 100


def _to_out(fault: FaultInjection, sensor: Sensor) -> FaultOut:
    return FaultOut(
        id=fault.id,
        simulation_run_id=fault.simulation_run_id,
        sensor_id=fault.sensor_id,
        sensor_code=sensor.code,
        sensor_type=sensor.sensor_type,
        fault_type=fault.fault_type,
        active=fault.active,
        magnitude=fault.magnitude,
        stuck_value=fault.stuck_value,
        start_simulation_time=fault.start_simulation_time,
        end_simulation_time=fault.end_simulation_time,
        started_at=fault.started_at,
        cleared_at=fault.cleared_at,
        reason=fault.reason,
        notes=fault.notes,
    )


async def _get_run(session: AsyncSession, run_id: uuid.UUID) -> SimulationRun:
    run = await session.get(SimulationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="simulation run not found")
    return run


async def _resolve_sensor(
    session: AsyncSession,
    run: SimulationRun,
    request: FaultInjectRequest,
) -> Sensor:
    if request.sensor_id is not None:
        sensor = await session.get(Sensor, request.sensor_id)
        if sensor is None or sensor.room_id != run.room_id:
            raise HTTPException(status_code=404, detail="sensor not found in run room")
        if request.sensor_type is not None and sensor.sensor_type is not request.sensor_type:
            raise HTTPException(status_code=422, detail="sensor_type does not match sensor_id")
        return sensor
    sensor = await session.scalar(
        select(Sensor).where(
            Sensor.room_id == run.room_id,
            Sensor.sensor_type == request.sensor_type,
        )
    )
    if sensor is None:
        raise HTTPException(status_code=404, detail="sensor not found in run room")
    return sensor


async def _default_stuck_value(
    session: AsyncSession,
    run: SimulationRun,
    sensor: Sensor,
) -> float:
    """주입 시점 최신 측정값. 이력이 없으면 참값."""
    latest = await session.scalar(
        select(SensorReading.value)
        .where(
            SensorReading.simulation_run_id == run.id,
            SensorReading.sensor_id == sensor.id,
            SensorReading.value.is_not(None),
        )
        .order_by(SensorReading.sequence.desc())
        .limit(1)
    )
    if latest is not None:
        return float(latest)
    state = await session.scalar(select(FarmState).where(FarmState.room_id == run.room_id))
    if state is None:
        raise HTTPException(status_code=404, detail="farm state not found for room")
    from app.services.simulation import environment_from_farm_state

    return true_value_for(environment_from_farm_state(state), sensor.sensor_type)


async def inject_fault(
    session: AsyncSession,
    run_id: uuid.UUID,
    request: FaultInjectRequest,
) -> FaultOut:
    run = await _get_run(session, run_id)
    if run.status is SimulationStatus.STOPPED:
        raise HTTPException(status_code=409, detail="cannot inject fault into stopped run")

    sensor = await _resolve_sensor(session, run, request)
    if sensor.sensor_type not in SIMULATED_SENSOR_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"sensor {sensor.code} has no simulated channel",
        )

    active = await session.scalar(
        select(FaultInjection).where(
            FaultInjection.simulation_run_id == run.id,
            FaultInjection.sensor_id == sensor.id,
            FaultInjection.active.is_(True),
        )
    )
    if active is not None:
        raise HTTPException(
            status_code=409,
            detail=f"sensor {sensor.code} already has active {active.fault_type.value} fault",
        )

    magnitude = request.magnitude
    stuck_value = request.stuck_value
    if request.fault_type is FaultType.SPIKE and magnitude is None:
        magnitude = DEFAULT_SPIKE_MAGNITUDE[sensor.sensor_type]
    if request.fault_type is FaultType.STUCK and stuck_value is None:
        stuck_value = await _default_stuck_value(session, run, sensor)

    fault = FaultInjection(
        simulation_run_id=run.id,
        sensor_id=sensor.id,
        fault_type=request.fault_type,
        active=True,
        magnitude=magnitude if request.fault_type is FaultType.SPIKE else None,
        stuck_value=stuck_value if request.fault_type is FaultType.STUCK else None,
        start_simulation_time=run.simulation_time_seconds,
        started_at=datetime.now(UTC),
        reason=request.reason,
    )
    session.add(fault)
    await session.commit()
    await session.refresh(fault)
    return _to_out(fault, sensor)


async def clear_fault(
    session: AsyncSession,
    run_id: uuid.UUID,
    fault_id: uuid.UUID,
    request: FaultClearRequest | None = None,
) -> FaultOut:
    run = await _get_run(session, run_id)
    fault = await session.get(FaultInjection, fault_id)
    if fault is None or fault.simulation_run_id != run.id:
        raise HTTPException(status_code=404, detail="fault not found in run")
    if not fault.active:
        raise HTTPException(status_code=409, detail="fault already cleared")

    fault.active = False
    fault.end_simulation_time = max(run.simulation_time_seconds, fault.start_simulation_time)
    fault.cleared_at = datetime.now(UTC)
    if request is not None and request.reason:
        fault.notes = f"cleared: {request.reason}"
    await session.commit()
    await session.refresh(fault)
    sensor = await session.get(Sensor, fault.sensor_id)
    assert sensor is not None
    return _to_out(fault, sensor)


async def list_run_faults(session: AsyncSession, run_id: uuid.UUID) -> FaultListOut:
    run = await _get_run(session, run_id)
    rows = (
        await session.execute(
            select(FaultInjection, Sensor)
            .join(Sensor, FaultInjection.sensor_id == Sensor.id)
            .where(FaultInjection.simulation_run_id == run.id)
            .order_by(FaultInjection.started_at.desc())
            .limit(FAULT_HISTORY_LIMIT)
        )
    ).all()
    return FaultListOut(
        run_id=run.id,
        faults=[_to_out(fault, sensor) for fault, sensor in rows],
    )


async def list_farm_faults(session: AsyncSession, farm_id: uuid.UUID) -> FaultListOut:
    """관제 UI 용 — 최신 run 의 고장 이력."""
    from app.services.farm import get_farm_or_404
    from app.services.telemetry import latest_run_for_farm

    await get_farm_or_404(session, farm_id)
    run = await latest_run_for_farm(session, farm_id)
    if run is None:
        return FaultListOut(run_id=None, faults=[])
    return await list_run_faults(session, run.id)


async def load_active_faults(
    session: AsyncSession,
    run_id: uuid.UUID,
) -> dict[SensorType, ActiveFault]:
    """step 이 측정에 적용할 진행 중 고장 (센서 타입별)."""
    rows = (
        await session.execute(
            select(FaultInjection, Sensor.sensor_type)
            .join(Sensor, FaultInjection.sensor_id == Sensor.id)
            .where(
                FaultInjection.simulation_run_id == run_id,
                FaultInjection.active.is_(True),
            )
        )
    ).all()
    return {
        sensor_type: ActiveFault(
            sensor_type=sensor_type,
            fault_type=fault.fault_type,
            start_simulation_time=fault.start_simulation_time,
            magnitude=fault.magnitude,
            stuck_value=fault.stuck_value,
        )
        for fault, sensor_type in rows
    }
