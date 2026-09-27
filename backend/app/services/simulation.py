"""
시뮬레이션 run 제어·스텝·readings batch (3단계 Day 11).

=============================================================================
책임 분리
-----------------------------------------------------------------------------
routers/simulations.py  → HTTP 경계
이 모듈 (services)      → 상태 전이·폐쇄 루프 일부·DB 커밋
domain/simulation/*     → 순수 계산 (시계·외기·환경·센서)

센서 noise 는 FarmState 에 절대 넣지 않는다.
참값 갱신(_apply_environment_to_farm_state) 과 측정(persist_samples) 을
코드 경로상으로도 분리한다. 측정 적재·품질 판정은 services.telemetry 와 공유한다.

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
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Actuator, FarmState, Sensor, SimulationRun, WeatherSnapshot
from app.domain.control.evaluate import MetricReading
from app.domain.enums import (
    ActuatorMode,
    ReadingSource,
    SensorType,
    SimulationStatus,
    WeatherMode,
)
from app.domain.simulation.config_loader import load_environment_params
from app.domain.simulation.environment import step_environment
from app.domain.simulation.sensors import SensorSample, VirtualSensorBank
from app.domain.simulation.state import (
    ActuatorInputs,
    EnvironmentState,
    OutdoorCondition,
)
from app.domain.simulation.weather import create_weather_adapter
from app.domain.telemetry import StreamQualityAssessor
from app.schemas.farm import ActuatorSummary
from app.schemas.simulation import SimulationRunOut, SimulationStepResult
from app.services.checkpoint import (
    capture_initial_state,
    restore_replay_start,
    scheduled_manual_actions,
    seed_gates,
    seed_stream_states,
)
from app.services.faults import load_fault_schedule
from app.services.manual_control import record_manual_command
from app.services.room_control import missing_reading, open_room_controller
from app.services.sender import SENDER_SEQUENCES
from app.services.telemetry import ReadingWriter, open_stream
from app.services.zone_runtime import advance_zones
from app.websocket.publisher import (
    publish_actuator_updated,
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


def environment_from_farm_state(state: FarmState) -> EnvironmentState:
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


def _replay_weather_samples(run: SimulationRun) -> list[tuple[float, float, float]] | None:
    """REPLAY 외기 run 의 (t, T, H) 시계열. 재생 run 이 아니면 None."""
    if run.weather_mode is not WeatherMode.REPLAY:
        return None
    rows = (run.replay_input or {}).get("weather") or []
    if not rows:
        raise HTTPException(status_code=409, detail="REPLAY run has no weather series")
    return [(float(t), float(temp), float(hum)) for t, temp, hum in rows]


async def _next_weather_sequence(session: AsyncSession, run_id: uuid.UUID) -> int:
    last = await session.scalar(
        select(func.max(WeatherSnapshot.sequence)).where(
            WeatherSnapshot.simulation_run_id == run_id
        )
    )
    return 1 if last is None else last + 1


def _apply_scheduled_manual(
    session: AsyncSession,
    run: SimulationRun,
    actuators_by_code: Mapping[str, Actuator],
    changed_ids: set[uuid.UUID],
    *,
    step_start: float,
    dt_seconds: float,
) -> bool:
    """재생 run 의 원본 수동 제어를 이 스텝 전에 적용하고 명령으로 남긴다."""
    applied = False
    for action in scheduled_manual_actions(
        run, step_start=step_start, dt_seconds=dt_seconds
    ):
        actuator = actuators_by_code.get(action["actuator_code"])
        if actuator is None:
            continue
        actuator.mode = ActuatorMode(action["mode"])
        actuator.output_ratio = float(action["output_ratio"])
        record_manual_command(
            session,
            run,
            actuator,
            simulation_time=float(action["simulation_time"]),
            now=datetime.now(UTC),
        )
        changed_ids.add(actuator.id)
        applied = True
    return applied


def actuator_inputs_from(actuators: Iterable[Actuator]) -> ActuatorInputs:
    """
    ORM Actuator 현재 운전 캐시 → 상태전이 입력 벡터.

    OFF 이면 effective 0.
    동일 타입 여러 대는 max (Day 9 ActuatorInputs.from_commands 와 동일 정책).
    """
    ratios = {
        "hvac": 0.0,
        "heater": 0.0,
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
        "heater": "heater",
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
        target = type_to_field.get(actuator.actuator_type.value)
        if target is None:
            continue
        if actuator.mode is ActuatorMode.OFF:
            continue
        ratios[target] = max(ratios[target], actuator.output_ratio)
    return ActuatorInputs(**ratios)


@dataclass(frozen=True)
class PersistResult:
    inserted: int
    readings: dict[SensorType, MetricReading]
    # 규칙 명령의 판정 근거 — dropout 센서는 행이 없어 빠진다
    reading_ids: dict[SensorType, uuid.UUID] = field(default_factory=dict)


def persist_samples(
    *,
    run_id: uuid.UUID,
    assessor: StreamQualityAssessor,
    writer: ReadingWriter,
    sensors_by_type: dict[SensorType, Sensor],
    samples: list[SensorSample],
    dropped_types: Iterable[SensorType] = (),
    sampled_at: datetime,
    ingested_at: datetime,
) -> PersistResult:
    """
    가상 센서 샘플을 스트림 품질 판정 후 append-only 로 추가한다.

    시뮬은 송신측이라 센서별 source_sequence 를 SENDER_SEQUENCES 로 발급한다.
    dropped_types(dropout) 는 번호만 소비하고 저장하지 않는다.
    룸에 해당 sensor_type 메타가 없으면 그 샘플은 skip.

    readings 는 규칙 입력 — 판정된 값·품질, dropout 은 MISSING.
    """
    inserted = 0
    readings: dict[SensorType, MetricReading] = {}
    reading_ids: dict[SensorType, uuid.UUID] = {}
    for sensor_type in dropped_types:
        sensor = sensors_by_type.get(sensor_type)
        if sensor is None:
            continue
        SENDER_SEQUENCES.issue(run_id, sensor.id, assessor)
        readings[sensor_type] = missing_reading(
            sensor_type, assessor.state_for(sensor.id).last_value
        )

    for sample in samples:
        sensor = sensors_by_type.get(sample.sensor_type)
        if sensor is None:
            continue
        source_sequence = SENDER_SEQUENCES.issue(run_id, sensor.id, assessor)
        assessment = assessor.assess(
            sensor.id,
            sensor_type=sample.sensor_type,
            source_sequence=source_sequence,
            value=sample.value,
            simulation_time=sample.simulation_time,
            base_quality=sample.quality,
            base_reason=sample.quality_reason,
            raw_value=sample.raw_value,
            sampled_at=sampled_at,
            ingested_at=ingested_at,
        )
        if assessment.verdict is not None:
            SENDER_SEQUENCES.delivered(run_id, sensor.id, source_sequence)
            readings[sample.sensor_type] = MetricReading(
                sensor_type=sample.sensor_type,
                value=sample.value,
                quality=assessment.verdict.quality,
            )
        inserted += writer.add(
            sensor=sensor,
            assessment=assessment,
            source_sequence=source_sequence,
            value=sample.value,
            raw_value=sample.raw_value,
            unit=sample.unit,
            input_unit=sample.input_unit,
            source=sample.source,
            simulation_time=sample.simulation_time,
            sampled_at=sampled_at,
            ingested_at=ingested_at,
            telemetry_schema_version=sample.telemetry_schema_version,
        )
        if assessment.verdict is not None and writer.last_reading_id is not None:
            reading_ids[sample.sensor_type] = writer.last_reading_id
    return PersistResult(inserted=inserted, readings=readings, reading_ids=reading_ids)


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
    4) (옵션) VirtualSensorBank.measure(활성 고장 적용) → 품질 판정·readings batch
    5) (옵션) 측정값·품질로 룸 규칙 평가 → Command/Event, 설비 갱신 (Day 22)

    persist_readings=False 면 측정이 없으므로 규칙도 돌리지 않는다.

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
    room_actuators = (
        await session.scalars(select(Actuator).where(Actuator.room_id == run.room_id))
    ).all()

    # Day 23: 재생 run 은 첫 스텝에 원본 체크포인트로 룸을 되돌리고,
    # 일반 run 은 첫 스텝 직전 상태를 체크포인트로 남긴다.
    replay_input = run.replay_input
    if replay_input is not None and not replay_input.get("restored"):
        if run.initial_state is None:
            raise HTTPException(status_code=409, detail="replay run has no checkpoint")
        restore_replay_start(run, farm_state, sensors, room_actuators)
    elif run.initial_state is None:
        run.initial_state = await capture_initial_state(
            session, run, farm_state, sensors, room_actuators
        )

    # 계수·외기·센서·설비는 스텝 루프 밖에서 한 번만 준비 (동일 입력 재현)
    params = load_environment_params()
    weather = create_weather_adapter(
        run.weather_mode.value,
        seed=run.random_seed,
        replay_samples=_replay_weather_samples(run),
    )
    sensor_bank = VirtualSensorBank(seed=run.random_seed)
    actuators = actuator_inputs_from(room_actuators)
    fault_schedule = await load_fault_schedule(
        session, run.id, since_simulation_time=run.simulation_time_seconds
    )
    controller = await open_room_controller(
        session,
        run,
        room_actuators,
        seed_gates=seed_gates(run.initial_state) if replay_input is not None else None,
    )
    run.rule_set_version = controller.rule_set_version
    weather_sequence = await _next_weather_sequence(session, run.id)
    actuators_by_code = {actuator.code: actuator for actuator in room_actuators}

    env = environment_from_farm_state(farm_state)
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
    assessor, writer = await open_stream(
        session,
        run,
        seed_states=(
            seed_stream_states(run.initial_state, sensors)
            if replay_input is not None
            else None
        ),
    )

    for _ in range(steps):
        # 재생 run: 원본이 이 스텝 전에 바꾼 수동 제어를 같은 시각으로 다시 적용
        if replay_input is not None and _apply_scheduled_manual(
            session,
            run,
            actuators_by_code,
            controller.changed_actuator_ids,
            step_start=env.simulation_time,
            dt_seconds=dt_seconds,
        ):
            actuators = actuator_inputs_from(room_actuators)

        # 스텝 끝 시각의 외기를 읽어 경계조건으로 사용
        outdoor = await weather.read(env.simulation_time + dt_seconds)
        wall_now = datetime.now(UTC)
        session.add(
            WeatherSnapshot(
                simulation_run_id=run.id,
                sequence=weather_sequence,
                source=run.weather_mode,
                outdoor_temperature_c=outdoor.temperature_c,
                outdoor_humidity_pct=outdoor.humidity_pct,
                simulation_time=env.simulation_time + dt_seconds,
                sampled_at=wall_now,
                ingested_at=wall_now,
            )
        )
        weather_sequence += 1
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

        # ② 측정은 참값 env 를 읽기만 한다 (Day 22: 활성 고장은 측정에만 적용)
        if persist_readings:
            faults = fault_schedule.active_at(env.simulation_time)
            samples = sensor_bank.measure(
                env, source=ReadingSource.SIMULATED, faults=faults
            )
            sampled_types = {sample.sensor_type for sample in samples}
            now = datetime.now(UTC)
            persisted = persist_samples(
                run_id=run.id,
                assessor=assessor,
                writer=writer,
                sensors_by_type=sensors_by_type,
                samples=samples,
                dropped_types=[
                    sensor_type
                    for sensor_type in faults
                    if sensor_type not in sampled_types
                ],
                sampled_at=now,
                ingested_at=now,
            )
            readings_inserted += persisted.inserted

            # ③ 측정값·품질로 룸 규칙 → 설비 변경은 다음 스텝 입력에 반영
            if controller.evaluate(
                persisted.readings,
                simulation_time=env.simulation_time,
                now=now,
                reading_ids=persisted.reading_ids,
            ):
                actuators = actuator_inputs_from(room_actuators)

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
        commands_issued=controller.commands_issued,
        control_blocked=controller.blocked_recorded,
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
    for actuator in room_actuators:
        if actuator.id in controller.changed_actuator_ids:
            await publish_actuator_updated(
                farm_id=run.farm_id,
                room_id=run.room_id,
                actuator_payload=ActuatorSummary.model_validate(actuator).model_dump(
                    mode="json"
                ),
            )
    return result
