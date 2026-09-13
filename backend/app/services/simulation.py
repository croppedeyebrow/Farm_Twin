"""
시뮬레이션 run 제어·스텝·readings batch (3단계 Day 11).

책임
----
- start / pause / resume / stop 상태 전이
- 한 스텝: 외기 → 환경 참값 → FarmState 갱신 → (선택) 센서 측정 batch
- 센서 noise 는 FarmState 에 절대 넣지 않는다

폐쇄 루프 중 Day 11 범위: 1~4 (+ commit). 규칙/명령은 4단계.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Actuator, FarmState, Sensor, SensorReading, SimulationRun
from app.domain.enums import (
    ActuatorMode,
    ReadingSource,
    SensorType,
    SimulationStatus,
)
from app.domain.simulation.config_loader import load_environment_params
from app.domain.simulation.environment import step_environment
from app.domain.simulation.sensors import VirtualSensorBank
from app.domain.simulation.state import (
    ActuatorInputs,
    EnvironmentState,
    OutdoorCondition,
)
from app.domain.simulation.weather import create_weather_adapter
from app.schemas.simulation import SimulationRunOut, SimulationStepResult

_ALLOWED_START = {
    SimulationStatus.CREATED,
    SimulationStatus.PAUSED,
    SimulationStatus.STOPPED,
}
_ALLOWED_PAUSE = {SimulationStatus.RUNNING}
_ALLOWED_RESUME = {SimulationStatus.PAUSED}
_ALLOWED_STOP = {SimulationStatus.RUNNING, SimulationStatus.PAUSED}
_ALLOWED_STEP = {SimulationStatus.RUNNING}


def _to_out(run: SimulationRun) -> SimulationRunOut:
    return SimulationRunOut.model_validate(run)


async def get_run_or_404(
    session: AsyncSession,
    run_id: uuid.UUID,
) -> SimulationRun:
    run = await session.get(SimulationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="simulation run not found")
    return run


async def list_runs(session: AsyncSession) -> list[SimulationRunOut]:
    result = await session.scalars(
        select(SimulationRun).order_by(SimulationRun.created_at.desc())
    )
    return [_to_out(run) for run in result.all()]


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> SimulationRunOut:
    return _to_out(await get_run_or_404(session, run_id))


async def start_run(session: AsyncSession, run_id: uuid.UUID) -> SimulationRunOut:
    """CREATED/PAUSED/STOPPED → RUNNING."""
    run = await get_run_or_404(session, run_id)
    if run.status not in _ALLOWED_START:
        raise HTTPException(
            status_code=409,
            detail=f"cannot start from status={run.status.value}",
        )
    now = datetime.now(UTC)
    run.status = SimulationStatus.RUNNING
    if run.started_at is None:
        run.started_at = now
    run.ended_at = None
    await session.commit()
    await session.refresh(run)
    return _to_out(run)


async def pause_run(session: AsyncSession, run_id: uuid.UUID) -> SimulationRunOut:
    """RUNNING → PAUSED. 가상 시계는 step 호출을 막아서 정지."""
    run = await get_run_or_404(session, run_id)
    if run.status not in _ALLOWED_PAUSE:
        raise HTTPException(
            status_code=409,
            detail=f"cannot pause from status={run.status.value}",
        )
    run.status = SimulationStatus.PAUSED
    await session.commit()
    await session.refresh(run)
    return _to_out(run)


async def resume_run(session: AsyncSession, run_id: uuid.UUID) -> SimulationRunOut:
    """PAUSED → RUNNING."""
    run = await get_run_or_404(session, run_id)
    if run.status not in _ALLOWED_RESUME:
        raise HTTPException(
            status_code=409,
            detail=f"cannot resume from status={run.status.value}",
        )
    run.status = SimulationStatus.RUNNING
    await session.commit()
    await session.refresh(run)
    return _to_out(run)


async def stop_run(session: AsyncSession, run_id: uuid.UUID) -> SimulationRunOut:
    """RUNNING/PAUSED → STOPPED."""
    run = await get_run_or_404(session, run_id)
    if run.status not in _ALLOWED_STOP:
        raise HTTPException(
            status_code=409,
            detail=f"cannot stop from status={run.status.value}",
        )
    run.status = SimulationStatus.STOPPED
    run.ended_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(run)
    return _to_out(run)


def _environment_from_farm_state(state: FarmState) -> EnvironmentState:
    return EnvironmentState(
        temperature_c=state.temperature_c,
        humidity_pct=state.humidity_pct,
        co2_ppm=state.co2_ppm,
        substrate_moisture_pct=state.substrate_moisture_pct,
        ppfd_umol=state.ppfd_umol,
        simulation_time=state.simulation_time,
    )


def _apply_environment_to_farm_state(
    farm_state: FarmState,
    env: EnvironmentState,
    *,
    run_id: uuid.UUID,
) -> None:
    """참값만 기록. 센서 noise 절대 금지."""
    farm_state.temperature_c = env.temperature_c
    farm_state.humidity_pct = env.humidity_pct
    farm_state.co2_ppm = env.co2_ppm
    farm_state.substrate_moisture_pct = env.substrate_moisture_pct
    farm_state.ppfd_umol = env.ppfd_umol
    farm_state.simulation_time = env.simulation_time
    farm_state.simulation_run_id = run_id
    farm_state.version = farm_state.version + 1


async def _load_actuator_inputs(
    session: AsyncSession,
    room_id: uuid.UUID,
) -> ActuatorInputs:
    actuators = (
        await session.scalars(select(Actuator).where(Actuator.room_id == room_id))
    ).all()
    ratios = {
        "hvac": 0.0,
        "ventilation_fan": 0.0,
        "dehumidifier": 0.0,
        "irrigation_pump": 0.0,
        "led": 0.0,
    }
    type_to_field = {
        "hvac": "hvac",
        "ventilation_fan": "ventilation_fan",
        "dehumidifier": "dehumidifier",
        "irrigation_pump": "irrigation_pump",
        "led": "led",
    }
    for actuator in actuators:
        field = type_to_field[actuator.actuator_type.value]
        if actuator.mode is ActuatorMode.OFF:
            continue
        ratios[field] = max(ratios[field], actuator.output_ratio)
    return ActuatorInputs(**ratios)


async def _next_reading_sequence(
    session: AsyncSession,
    run_id: uuid.UUID,
) -> int:
    current = await session.scalar(
        select(func.coalesce(func.max(SensorReading.sequence), -1)).where(
            SensorReading.simulation_run_id == run_id
        )
    )
    return int(current) + 1


async def persist_readings_batch(
    session: AsyncSession,
    *,
    run: SimulationRun,
    sensors_by_type: dict[SensorType, Sensor],
    samples: list,
    sequence_start: int,
    sampled_at: datetime,
    ingested_at: datetime,
) -> int:
    """
    SensorSample 목록을 sensor_readings 에 append-only batch insert.

    sequence 는 run 내에서 단조 증가 (UNIQUE(run_id, sequence)).
    """
    sequence = sequence_start
    inserted = 0
    for sample in samples:
        sensor = sensors_by_type.get(sample.sensor_type)
        if sensor is None:
            continue
        session.add(
            SensorReading(
                sensor_id=sensor.id,
                farm_id=run.farm_id,
                room_id=run.room_id,
                simulation_run_id=run.id,
                sequence=sequence,
                value=sample.value,
                unit=sample.unit,
                quality=sample.quality,
                source=sample.source,
                sensor_model_version=sensor.model_version,
                simulation_time=sample.simulation_time,
                sampled_at=sampled_at,
                ingested_at=ingested_at,
            )
        )
        sequence += 1
        inserted += 1
    return inserted


async def step_run(
    session: AsyncSession,
    run_id: uuid.UUID,
    *,
    steps: int = 1,
    dt_seconds: float = 60.0,
    persist_readings: bool = True,
) -> SimulationStepResult:
    """
    RUNNING run 을 N 스텝 전진한다.

    각 스텝:
      1) weather.read(t)
      2) step_environment → 참값
      3) FarmState 갱신 (noise 없음)
      4) VirtualSensorBank.measure → readings batch (옵션)
    """
    if steps < 1:
        raise HTTPException(status_code=400, detail="steps must be >= 1")
    if dt_seconds <= 0:
        raise HTTPException(status_code=400, detail="dt_seconds must be > 0")

    run = await get_run_or_404(session, run_id)
    if run.status not in _ALLOWED_STEP:
        raise HTTPException(
            status_code=409,
            detail=f"cannot step from status={run.status.value}; start the run first",
        )

    farm_state = await session.scalar(
        select(FarmState).where(FarmState.room_id == run.room_id)
    )
    if farm_state is None:
        raise HTTPException(status_code=404, detail="farm state not found for room")

    sensors = (
        await session.scalars(select(Sensor).where(Sensor.room_id == run.room_id))
    ).all()
    sensors_by_type = {sensor.sensor_type: sensor for sensor in sensors}

    params = load_environment_params()
    weather = create_weather_adapter(run.weather_mode.value, seed=run.random_seed)
    sensor_bank = VirtualSensorBank(seed=run.random_seed)
    actuators = await _load_actuator_inputs(session, run.room_id)

    env = _environment_from_farm_state(farm_state)
    # DB 시각과 도메인 시각 동기화 (재시작 복구)
    env = EnvironmentState(
        temperature_c=env.temperature_c,
        humidity_pct=env.humidity_pct,
        co2_ppm=env.co2_ppm,
        substrate_moisture_pct=env.substrate_moisture_pct,
        ppfd_umol=env.ppfd_umol,
        simulation_time=run.simulation_time_seconds,
    )

    readings_inserted = 0
    sequence = await _next_reading_sequence(session, run.id)

    for _ in range(steps):
        outdoor = await weather.read(env.simulation_time + dt_seconds)
        # OutdoorCondition.simulation_time 을 스텝 끝에 맞춤
        outdoor = OutdoorCondition(
            temperature_c=outdoor.temperature_c,
            humidity_pct=outdoor.humidity_pct,
            simulation_time=env.simulation_time + dt_seconds,
            source=outdoor.source,
            co2_ppm=outdoor.co2_ppm,
        )
        env = step_environment(
            env,
            outdoor=outdoor,
            actuators=actuators,
            dt_seconds=dt_seconds,
            params=params,
        )
        _apply_environment_to_farm_state(farm_state, env, run_id=run.id)
        run.simulation_time_seconds = env.simulation_time

        if persist_readings:
            samples = sensor_bank.measure(env, source=ReadingSource.SIMULATED)
            now = datetime.now(UTC)
            count = await persist_readings_batch(
                session,
                run=run,
                sensors_by_type=sensors_by_type,
                samples=samples,
                sequence_start=sequence,
                sampled_at=now,
                ingested_at=now,
            )
            sequence += count
            readings_inserted += count

    await session.commit()
    await session.refresh(farm_state)
    await session.refresh(run)

    return SimulationStepResult(
        run_id=run.id,
        status=run.status,
        steps_applied=steps,
        simulation_time_seconds=run.simulation_time_seconds,
        farm_state_version=farm_state.version,
        readings_inserted=readings_inserted,
        temperature_c=farm_state.temperature_c,
        humidity_pct=farm_state.humidity_pct,
        co2_ppm=farm_state.co2_ppm,
        substrate_moisture_pct=farm_state.substrate_moisture_pct,
        ppfd_umol=farm_state.ppfd_umol,
    )
