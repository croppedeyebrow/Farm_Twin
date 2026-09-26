"""
시뮬레이션 run 제어·스텝·readings batch (3단계 Day 11).

=============================================================================
책임 분리
-----------------------------------------------------------------------------
routers/simulations.py  → HTTP 경계
이 모듈 (services)      → 상태 전이·폐쇄 루프 일부·DB 커밋
domain/simulation/*     → 순수 계산 (시계·외기·환경·센서)

센서 noise 는 FarmState 에 절대 넣지 않는다.
참값 갱신(_apply_environment_to_farm_state) 과 측정(persist_readings_batch) 을
코드 경로상으로도 분리한다.

=============================================================================
상태 기계 (SimulationStatus)
-----------------------------------------------------------------------------
    CREATED ──start──► RUNNING ◄──resume── PAUSED
                 │         │                  ▲
                 │       pause                │
                 │         └──────────────────┘
                 │         │
                 │        stop
                 ▼         ▼
              STOPPED ◄────┘

잘못된 전이는 409 Conflict.
step 은 RUNNING 에서만 허용 (pause = 가상 시계 정지와 동일 효과).

=============================================================================
폐쇄 루프에서 Day 11 + Day 16
-----------------------------------------------------------------------------
백엔드 설계 6절 순서 중:
  1 외기·FarmState 로드
  2 액추에이터 상태 반영
  3 다음 FarmState 계산
  4 가상 센서 측정
  …
  10 DB commit **성공 후** 실시간 이벤트 발행 (websocket.publisher)

규칙/명령/이벤트(5~9)는 4단계 도메인.
발행은 이 서비스의 commit 직후에만 호출한다 (commit 전 push 금지).
push 실패는 publisher 가 삼키므로 API 응답·DB 상태는 유지된다.
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
from app.services.zone_runtime import advance_zones
from app.websocket.publisher import (
    publish_farm_state_updated,
    publish_simulation_status,
)

# 허용 전이 집합 — 문서의 상태 기계와 1:1
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
    """ORM → API 스키마."""
    return SimulationRunOut.model_validate(run)


async def get_run_or_404(
    session: AsyncSession,
    run_id: uuid.UUID,
) -> SimulationRun:
    """없으면 404. 서비스 내부 공통 가드."""
    run = await session.get(SimulationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="simulation run not found")
    return run


async def list_runs(session: AsyncSession) -> list[SimulationRunOut]:
    """최신 생성순 run 목록."""
    result = await session.scalars(
        select(SimulationRun).order_by(SimulationRun.created_at.desc())
    )
    return [_to_out(run) for run in result.all()]


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> SimulationRunOut:
    """단건 조회."""
    return _to_out(await get_run_or_404(session, run_id))


async def start_run(session: AsyncSession, run_id: uuid.UUID) -> SimulationRunOut:
    """
    CREATED / PAUSED / STOPPED → RUNNING.

    - 최초 start 때만 started_at 기록 (재시작 시 최초 시각 보존)
    - ended_at 은 비워 다시 달릴 수 있게 한다
    """
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
    out = _to_out(run)
    # Day 16: commit 확정 후에만 WS push (실패해도 HTTP/DB 결과는 유지)
    await publish_simulation_status(out)
    return out


async def pause_run(session: AsyncSession, run_id: uuid.UUID) -> SimulationRunOut:
    """
    RUNNING → PAUSED.

    가상 시계를 멈추는 방법은 step 을 거부하는 것.
    (SimulationClock.pause 와 같은 의미, DB 상태 플래그로 표현)
    """
    run = await get_run_or_404(session, run_id)
    if run.status not in _ALLOWED_PAUSE:
        raise HTTPException(
            status_code=409,
            detail=f"cannot pause from status={run.status.value}",
        )
    run.status = SimulationStatus.PAUSED
    await session.commit()
    await session.refresh(run)
    out = _to_out(run)
    await publish_simulation_status(out)  # Day 16 commit-then-push
    return out


async def resume_run(session: AsyncSession, run_id: uuid.UUID) -> SimulationRunOut:
    """PAUSED → RUNNING. 마지막 committed FarmState / simulation_time 부터 이어간다."""
    run = await get_run_or_404(session, run_id)
    if run.status not in _ALLOWED_RESUME:
        raise HTTPException(
            status_code=409,
            detail=f"cannot resume from status={run.status.value}",
        )
    run.status = SimulationStatus.RUNNING
    await session.commit()
    await session.refresh(run)
    out = _to_out(run)
    await publish_simulation_status(out)  # Day 16 commit-then-push
    return out


async def stop_run(session: AsyncSession, run_id: uuid.UUID) -> SimulationRunOut:
    """RUNNING / PAUSED → STOPPED. ended_at = wall-clock 종료 시각."""
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
    out = _to_out(run)
    await publish_simulation_status(out)  # Day 16 commit-then-push
    return out


def _environment_from_farm_state(state: FarmState) -> EnvironmentState:
    """DB 참값 스냅샷 → 도메인 EnvironmentState (ORM 의존을 step 밖으로)."""
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
    """
    환경 모델 출력(참값)만 FarmState 에 기록한다.

    센서 sample.value 를 여기 넣으면 불변조건 위반.
    version 은 갱신마다 +1 (낙관적 동시성·관측용).
    """
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
    """
    ORM Actuator 현재 운전 캐시 → 상태전이 입력 벡터.

    OFF 이면 effective 0.
    동일 타입 여러 대는 max (Day 9 ActuatorInputs.from_commands 와 동일 정책).
    """
    actuators = (
        await session.scalars(select(Actuator).where(Actuator.room_id == room_id))
    ).all()
    ratios = {
        "hvac": 0.0,
        "ventilation_fan": 0.0,
        "dehumidifier": 0.0,
        "irrigation_pump": 0.0,
        "led": 0.0,
        "circulation_fan": 0.0,
        "humidifier": 0.0,
        "zone_valve_strawberry": 0.0,
        "zone_valve_grape": 0.0,
        "dosing_pump": 0.0,
        "shade_curtain": 0.0,
        "vent_motor": 0.0,
    }
    type_to_field = {
        "hvac": "hvac",
        "ventilation_fan": "ventilation_fan",
        "dehumidifier": "dehumidifier",
        "irrigation_pump": "irrigation_pump",
        "led": "led",
        "circulation_fan": "circulation_fan",
        "humidifier": "humidifier",
        "zone_valve_strawberry": "zone_valve_strawberry",
        "zone_valve_grape": "zone_valve_grape",
        "dosing_pump": "dosing_pump",
        "shade_curtain": "shade_curtain",
        "vent_motor": "vent_motor",
    }
    for actuator in actuators:
        field = type_to_field.get(actuator.actuator_type.value)
        if field is None:
            continue
        if actuator.mode is ActuatorMode.OFF:
            continue
        ratios[field] = max(ratios[field], actuator.output_ratio)
    return ActuatorInputs(**ratios)


async def _next_reading_sequence(
    session: AsyncSession,
    run_id: uuid.UUID,
) -> int:
    """
    run 내 sequence 다음 값.

    UNIQUE(simulation_run_id, sequence) 를 지키려면
    max(sequence)+1 부터 batch 를 채워야 한다. 행이 없으면 0.
    """
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

    - 원본 수정 금지 (UPDATE 없음)
    - 룸에 해당 sensor_type 메타가 없으면 그 샘플은 skip
    - sampled_at / ingested_at: 시간_컬럼_의미.md (원본 샘플 vs 적재 시각)
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
                raw_value=sample.raw_value,
                unit=sample.unit,
                input_unit=sample.input_unit,
                quality=sample.quality,
                quality_reason=sample.quality_reason,
                telemetry_schema_version=sample.telemetry_schema_version,
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

    각 스텝
    -------
    1) weather.read(t+dt) — 외기 경계조건
    2) step_environment — 참값 오일러 적분
    3) FarmState / run.simulation_time_seconds 갱신 (noise 없음)
    4) (옵션) VirtualSensorBank.measure → readings batch

    재시작 복구
    -----------
    env.simulation_time 은 run.simulation_time_seconds 로 맞춘다.
    (FarmState.simulation_time 과 어긋날 수 있는 과거 버그/부분 커밋 대비)

    worker(simulator/app/runner.py) 와 API POST .../step 가 이 함수를 공유한다.
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

    # 계수·외기·센서·설비는 스텝 루프 밖에서 한 번만 준비 (동일 입력 재현)
    params = load_environment_params()
    weather = create_weather_adapter(run.weather_mode.value, seed=run.random_seed)
    sensor_bank = VirtualSensorBank(seed=run.random_seed)
    actuators = await _load_actuator_inputs(session, run.room_id)

    env = _environment_from_farm_state(farm_state)
    # 커밋된 run 시계를 도메인 상태의 권위 있는 시각으로 사용
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
        # 스텝 끝 시각의 외기를 읽어 경계조건으로 사용
        outdoor = await weather.read(env.simulation_time + dt_seconds)
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
        # ① 참값 커밋 대상 갱신 (측정 전)
        _apply_environment_to_farm_state(farm_state, env, run_id=run.id)
        run.simulation_time_seconds = env.simulation_time

        # ①-b 작물 구역 전진 (관수·병해완화·LED/DLI 폐쇄루프)
        # 목적: 룸 FarmState 커밋 직후 구역 캐시를 같은 dt 로 맞춘다.
        # 이유: snapshot.zones 가 시뮬 시각과 어긋나면 관제 UI 인과가 깨진다.
        advance_zones(
            run.farm_id,
            room=env,
            actuators=actuators,
            dt_seconds=dt_seconds,
        )

        # ② 측정은 참값 env 를 읽기만 한다
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

    result = SimulationStepResult(
        run_id=run.id,
        status=run.status,
        steps_applied=steps,
        simulation_time_seconds=run.simulation_time_seconds,
        farm_state_version=farm_state.version,
        readings_inserted=readings_inserted,
        # 응답의 환경 필드는 항상 FarmState 참값 (readings 가 아님)
        temperature_c=farm_state.temperature_c,
        humidity_pct=farm_state.humidity_pct,
        co2_ppm=farm_state.co2_ppm,
        substrate_moisture_pct=farm_state.substrate_moisture_pct,
        ppfd_umol=farm_state.ppfd_umol,
    )
    # Day 16: DB 반영 확정 후에만 관제 스트림 push (farm_state.updated)
    # 구독자 없거나 push 실패해도 result 는 그대로 반환한다.
    await publish_farm_state_updated(
        farm_id=run.farm_id,
        room_id=run.room_id,
        result=result,
    )
    return result
