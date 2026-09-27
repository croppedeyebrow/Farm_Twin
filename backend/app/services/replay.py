"""
재생 데이터셋 export / import / 실행 / 비교 (6단계 Day 23).

=============================================================================
흐름
-----------------------------------------------------------------------------
  export  : 원본 run → farmtwin.replay.v1 JSON
            (체크포인트·외기·스텝 간격·고장·수동 제어 + 기대 readings/commands)
  import  : 데이터셋 → 새 재생 run (CREATED, replay_of_run_id = 원본)
            고장은 원본 시각 그대로 fault_injections 로, 나머지는 replay_input 으로
  run     : 원본 스텝 간격대로 step_run 을 호출하고 끝나면 STOPPED
  compare : 재생 run 결과 ↔ 기대 결과. 전부 같으면 reproduced=True

=============================================================================
재현 조건
-----------------------------------------------------------------------------
같은 seed·같은 출발 상태·같은 외기·같은 고장/수동 시각·같은 규칙이면
센서 noise(시각 기반 결정적 난수)·품질 판정·규칙 명령이 모두 같게 나온다.
규칙은 현재 룸 규칙을 쓰므로 지문(rule_set_version)이 다르면 비교에 표시된다.

재생 run 은 원본과 같은 룸(FarmState)을 쓴다. 실행 전에 같은 룸의 RUNNING run 을
PAUSED 로 돌려 두 run 이 한 룸 상태를 번갈아 덮지 않게 한다.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Actuator,
    ControlCommand,
    ControlRule,
    FaultInjection,
    Room,
    Sensor,
    SensorReading,
    SimulationRun,
    WeatherSnapshot,
)
from app.domain.enums import SimulationStatus, WeatherMode
from app.schemas.replay import (
    REPLAY_DATASET_FORMAT,
    CommandMismatch,
    ReadingMismatch,
    ReplayCompareOut,
    ReplayDataset,
    ReplayFault,
    ReplayImportRequest,
    ReplayManualAction,
    ReplayRule,
    ReplayRunMeta,
    ReplayRunOut,
)
from app.schemas.simulation import SimulationRunOut
from app.services import simulation as simulation_service
from app.services.manual_control import MANUAL_REASON

# step_run 한 호출(한 트랜잭션)에 묶는 최대 스텝
REPLAY_CHUNK_STEPS = 1440
MISMATCH_SAMPLE_LIMIT = 20
_TOLERANCE = 1e-9


def _checkpoint_time(initial_state: dict[str, Any]) -> float:
    return float(initial_state.get("simulation_time") or 0.0)


def _step_plan(times: list[float], start: float) -> list[tuple[float, int]]:
    """스텝 끝 시각 목록 → 같은 dt 끼리 묶은 [(dt, n)]."""
    plan: list[tuple[float, int]] = []
    previous = start
    for t in times:
        dt = round(t - previous, 6)
        previous = t
        if dt <= 0:
            continue
        if plan and plan[-1][0] == dt:
            plan[-1] = (dt, plan[-1][1] + 1)
        else:
            plan.append((dt, 1))
    return plan


def _plan_end(start: float, plan: list[tuple[float, int]]) -> float:
    # step_environment 와 같은 누적 덧셈으로 끝 시각을 구한다
    t = start
    for dt, count in plan:
        for _ in range(count):
            t = t + dt
    return t


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


async def export_dataset(session: AsyncSession, run_id: uuid.UUID) -> ReplayDataset:
    run = await simulation_service.get_run_or_404(session, run_id)
    if run.initial_state is None:
        raise HTTPException(
            status_code=409,
            detail="run has no checkpoint yet — step the run at least once",
        )
    room = await session.get(Room, run.room_id)
    assert room is not None
    t0 = _checkpoint_time(run.initial_state)
    streams = run.initial_state.get("streams") or {}

    rules = (
        await session.scalars(
            select(ControlRule)
            .where(ControlRule.room_id == run.room_id)
            .order_by(ControlRule.priority, ControlRule.name)
        )
    ).all()
    sensors = (
        await session.scalars(
            select(Sensor).where(Sensor.room_id == run.room_id).order_by(Sensor.code)
        )
    ).all()
    actuators = (
        await session.scalars(
            select(Actuator).where(Actuator.room_id == run.room_id).order_by(Actuator.code)
        )
    ).all()

    snapshots = (
        await session.scalars(
            select(WeatherSnapshot)
            .where(
                WeatherSnapshot.simulation_run_id == run.id,
                WeatherSnapshot.simulation_time > t0,
            )
            .order_by(WeatherSnapshot.sequence)
        )
    ).all()
    weather = [
        (row.simulation_time, row.outdoor_temperature_c, row.outdoor_humidity_pct)
        for row in snapshots
    ]

    fault_rows = (
        await session.execute(
            select(FaultInjection, Sensor.code)
            .join(Sensor, FaultInjection.sensor_id == Sensor.id)
            .where(
                FaultInjection.simulation_run_id == run.id,
                or_(
                    FaultInjection.end_simulation_time.is_(None),
                    FaultInjection.end_simulation_time >= t0,
                ),
            )
            .order_by(FaultInjection.start_simulation_time)
        )
    ).all()

    reading_rows = (
        await session.execute(
            select(SensorReading, Sensor.code)
            .join(Sensor, SensorReading.sensor_id == Sensor.id)
            .where(SensorReading.simulation_run_id == run.id)
            .order_by(SensorReading.sequence)
        )
    ).all()
    readings: list[tuple[str, int | None, float, float | None, float | None, str]] = []
    for reading, code in reading_rows:
        last_sequence = (streams.get(code) or {}).get("last_sequence")
        if reading.source_sequence is not None and last_sequence is not None:
            if reading.source_sequence <= last_sequence:
                continue
        elif reading.simulation_time <= t0:
            continue
        readings.append(
            (
                code,
                reading.source_sequence,
                reading.simulation_time,
                reading.raw_value,
                reading.value,
                reading.quality.value,
            )
        )

    command_rows = (
        await session.execute(
            select(ControlCommand, Actuator.code, ControlRule.name)
            .join(Actuator, ControlCommand.actuator_id == Actuator.id)
            .outerjoin(ControlRule, ControlCommand.rule_id == ControlRule.id)
            .where(
                ControlCommand.simulation_run_id == run.id,
                ControlCommand.simulation_time > t0,
            )
            .order_by(ControlCommand.simulation_time, ControlCommand.issued_at)
        )
    ).all()
    commands = [
        (
            command.simulation_time,
            code,
            command.desired_mode.value,
            command.desired_output_ratio,
            command.status.value,
            rule_name or MANUAL_REASON,
        )
        for command, code, rule_name in command_rows
    ]
    manual_actions = [
        ReplayManualAction(
            simulation_time=command.simulation_time,
            actuator_code=code,
            mode=command.desired_mode,
            output_ratio=command.desired_output_ratio,
        )
        for command, code, rule_name in command_rows
        if rule_name is None and command.reason == MANUAL_REASON
    ]

    return ReplayDataset(
        format=REPLAY_DATASET_FORMAT,
        exported_at=datetime.now(UTC),
        run=ReplayRunMeta(
            id=run.id,
            name=run.name,
            farm_id=run.farm_id,
            room_id=run.room_id,
            room_code=room.code,
            status=run.status,
            random_seed=run.random_seed,
            weather_mode=run.weather_mode,
            environment_model_version=run.environment_model_version,
            rule_set_version=run.rule_set_version,
            simulation_time_seconds=run.simulation_time_seconds,
            replay_of_run_id=run.replay_of_run_id,
        ),
        initial_state=run.initial_state,
        rules=[
            ReplayRule(
                name=rule.name,
                version=rule.version,
                enabled=rule.enabled,
                priority=rule.priority,
                metric=rule.metric.value,
                comparator=rule.comparator.value,
                start_threshold=rule.start_threshold,
                stop_threshold=rule.stop_threshold,
                target_actuator_type=rule.target_actuator_type.value,
                target_mode=rule.target_mode.value,
                target_output_ratio=rule.target_output_ratio,
                cooldown_seconds=rule.cooldown_seconds,
                min_on_seconds=rule.min_on_seconds,
            )
            for rule in rules
        ],
        sensor_codes=[sensor.code for sensor in sensors],
        actuator_codes=[actuator.code for actuator in actuators],
        steps=_step_plan([row[0] for row in weather], t0),
        weather=weather,
        faults=[
            ReplayFault(
                sensor_code=code,
                fault_type=fault.fault_type,
                magnitude=fault.magnitude,
                stuck_value=fault.stuck_value,
                start_simulation_time=fault.start_simulation_time,
                end_simulation_time=fault.end_simulation_time,
                reason=fault.reason,
            )
            for fault, code in fault_rows
        ],
        manual_actions=manual_actions,
        readings=readings,
        commands=commands,
    )


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------


async def _resolve_room(session: AsyncSession, dataset: ReplayDataset) -> Room:
    room = await session.get(Room, dataset.run.room_id)
    if room is None:
        room = await session.scalar(
            select(Room).where(Room.code == dataset.run.room_code).limit(1)
        )
    if room is None:
        raise HTTPException(
            status_code=422,
            detail=f"room {dataset.run.room_code} not found for replay",
        )
    return room


async def import_dataset(
    session: AsyncSession,
    request: ReplayImportRequest,
) -> SimulationRunOut:
    dataset = request.dataset
    if not dataset.steps:
        raise HTTPException(status_code=422, detail="dataset has no steps to replay")
    if "farm_state" not in dataset.initial_state:
        raise HTTPException(status_code=422, detail="dataset initial_state has no farm_state")

    room = await _resolve_room(session, dataset)
    sensors = {
        sensor.code: sensor
        for sensor in (
            await session.scalars(select(Sensor).where(Sensor.room_id == room.id))
        ).all()
    }
    actuator_codes = set(
        (
            await session.scalars(select(Actuator.code).where(Actuator.room_id == room.id))
        ).all()
    )

    needed_sensors = (
        {fault.sensor_code for fault in dataset.faults}
        | {row[0] for row in dataset.readings}
        | set((dataset.initial_state.get("streams") or {}).keys())
    )
    missing_sensors = sorted(needed_sensors - set(sensors))
    if missing_sensors:
        raise HTTPException(
            status_code=422,
            detail=f"sensors not found in room: {', '.join(missing_sensors)}",
        )
    needed_actuators = {action.actuator_code for action in dataset.manual_actions} | {
        item["code"] for item in dataset.initial_state.get("actuators") or []
    }
    missing_actuators = sorted(needed_actuators - actuator_codes)
    if missing_actuators:
        raise HTTPException(
            status_code=422,
            detail=f"actuators not found in room: {', '.join(missing_actuators)}",
        )

    source = await session.get(SimulationRun, dataset.run.id)
    t0 = _checkpoint_time(dataset.initial_state)
    plan = [(float(dt), int(count)) for dt, count in dataset.steps]
    weather_mode = WeatherMode.REPLAY if dataset.weather else dataset.run.weather_mode

    run = SimulationRun(
        id=uuid.uuid4(),
        farm_id=room.farm_id,
        room_id=room.id,
        name=(request.name or f"replay · {dataset.run.name}")[:120],
        status=SimulationStatus.CREATED,
        random_seed=dataset.run.random_seed,
        weather_mode=weather_mode,
        environment_model_version=dataset.run.environment_model_version,
        simulation_time_seconds=t0,
        initial_state=dataset.initial_state,
        replay_of_run_id=source.id if source is not None else None,
        notes=f"{REPLAY_DATASET_FORMAT} import of run {dataset.run.id}",
        replay_input={
            "format": REPLAY_DATASET_FORMAT,
            "source_run_id": str(dataset.run.id),
            "source_run_name": dataset.run.name,
            "checkpoint_time": t0,
            "end_simulation_time": _plan_end(t0, plan),
            "steps": [[dt, count] for dt, count in plan],
            "weather": [list(row) for row in dataset.weather],
            "manual_actions": [
                action.model_dump(mode="json")
                for action in dataset.manual_actions
                if action.simulation_time > t0
            ],
            "rule_set_version": dataset.run.rule_set_version,
            "restored": False,
            "expected": {
                "readings": [list(row) for row in dataset.readings],
                "commands": [list(row) for row in dataset.commands],
            },
        },
    )
    session.add(run)
    now = datetime.now(UTC)
    for fault in dataset.faults:
        session.add(
            FaultInjection(
                simulation_run_id=run.id,
                sensor_id=sensors[fault.sensor_code].id,
                fault_type=fault.fault_type,
                active=fault.end_simulation_time is None,
                magnitude=fault.magnitude,
                stuck_value=fault.stuck_value,
                start_simulation_time=fault.start_simulation_time,
                end_simulation_time=fault.end_simulation_time,
                started_at=now,
                cleared_at=now if fault.end_simulation_time is not None else None,
                reason=fault.reason,
                notes="replay import",
            )
        )
    await session.commit()
    await session.refresh(run)
    return SimulationRunOut.model_validate(run)


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


async def _get_replay_run(session: AsyncSession, run_id: uuid.UUID) -> SimulationRun:
    run = await simulation_service.get_run_or_404(session, run_id)
    if run.replay_input is None:
        raise HTTPException(status_code=409, detail="run is not a replay run")
    return run


async def _steps_done(session: AsyncSession, run_id: uuid.UUID) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(WeatherSnapshot)
        .where(WeatherSnapshot.simulation_run_id == run_id)
    )
    return int(count or 0)


def _remaining_chunks(
    plan: list[tuple[float, int]],
    *,
    done: int,
    budget: int,
) -> list[tuple[float, int]]:
    chunks: list[tuple[float, int]] = []
    skip = done
    for dt, count in plan:
        if skip >= count:
            skip -= count
            continue
        available = count - skip
        skip = 0
        while available > 0 and budget > 0:
            take = min(available, budget, REPLAY_CHUNK_STEPS)
            chunks.append((dt, take))
            available -= take
            budget -= take
        if budget <= 0:
            break
    return chunks


async def run_replay(
    session: AsyncSession,
    run_id: uuid.UUID,
    *,
    max_steps: int,
) -> ReplayRunOut:
    run = await _get_replay_run(session, run_id)
    plan = [(float(dt), int(count)) for dt, count in run.replay_input["steps"]]
    total = sum(count for _, count in plan)

    others = (
        await session.scalars(
            select(SimulationRun).where(
                SimulationRun.room_id == run.room_id,
                SimulationRun.id != run.id,
                SimulationRun.status == SimulationStatus.RUNNING,
            )
        )
    ).all()
    paused_run_ids = [other.id for other in others]
    for other in others:
        await simulation_service.pause_run(session, other.id)

    done = await _steps_done(session, run.id)
    chunks = _remaining_chunks(plan, done=done, budget=max_steps)
    if chunks and run.status is not SimulationStatus.RUNNING:
        if run.status is SimulationStatus.PAUSED:
            await simulation_service.resume_run(session, run.id)
        else:
            await simulation_service.start_run(session, run.id)

    applied = 0
    for dt, count in chunks:
        await simulation_service.step_run(session, run.id, steps=count, dt_seconds=dt)
        applied += count

    remaining = total - done - applied
    await session.refresh(run)
    if remaining <= 0 and run.status is not SimulationStatus.STOPPED:
        await simulation_service.stop_run(session, run.id)

    return ReplayRunOut(
        run_id=run.id,
        steps_applied=applied,
        steps_remaining=max(remaining, 0),
        paused_run_ids=paused_run_ids,
        compare=await compare_replay(session, run.id),
    )


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


def _close(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if math.isnan(a) or math.isnan(b):
            return math.isnan(a) and math.isnan(b)
        return abs(float(a) - float(b)) <= _TOLERANCE
    return a == b


def _rows_equal(expected: list[Any], actual: list[Any]) -> bool:
    return len(expected) == len(actual) and all(
        _close(left, right) for left, right in zip(expected, actual, strict=True)
    )


def _command_key(row: list[Any]) -> tuple[Any, ...]:
    return (round(float(row[0]), 6), row[1], row[5], row[4], row[2])


async def compare_replay(session: AsyncSession, run_id: uuid.UUID) -> ReplayCompareOut:
    run = await _get_replay_run(session, run_id)
    replay_input = run.replay_input
    t_now = run.simulation_time_seconds
    end = float(replay_input["end_simulation_time"])
    expected_payload = replay_input.get("expected") or {}

    expected_readings = {
        (row[0], row[1]): row
        for row in expected_payload.get("readings") or []
        if float(row[2]) <= t_now + _TOLERANCE
    }
    reading_rows = (
        await session.execute(
            select(SensorReading, Sensor.code)
            .join(Sensor, SensorReading.sensor_id == Sensor.id)
            .where(SensorReading.simulation_run_id == run.id)
            .order_by(SensorReading.sequence)
        )
    ).all()
    actual_readings = {
        (code, reading.source_sequence): [
            code,
            reading.source_sequence,
            reading.simulation_time,
            reading.raw_value,
            reading.value,
            reading.quality.value,
        ]
        for reading, code in reading_rows
    }

    matched = 0
    mismatches: list[ReadingMismatch] = []
    missing = 0
    for key, expected in expected_readings.items():
        actual = actual_readings.get(key)
        if actual is None:
            missing += 1
        elif _rows_equal(list(expected), actual):
            matched += 1
            continue
        if len(mismatches) < MISMATCH_SAMPLE_LIMIT:
            mismatches.append(
                ReadingMismatch(
                    sensor_code=key[0],
                    source_sequence=key[1],
                    simulation_time=float(expected[2]),
                    expected=list(expected),
                    actual=actual,
                )
            )
    extra = len(set(actual_readings) - set(expected_readings))
    mismatched = len(expected_readings) - matched - missing

    expected_commands = sorted(
        (
            list(row)
            for row in expected_payload.get("commands") or []
            if float(row[0]) <= t_now + _TOLERANCE
        ),
        key=_command_key,
    )
    command_rows = (
        await session.execute(
            select(ControlCommand, Actuator.code, ControlRule.name)
            .join(Actuator, ControlCommand.actuator_id == Actuator.id)
            .outerjoin(ControlRule, ControlCommand.rule_id == ControlRule.id)
            .where(ControlCommand.simulation_run_id == run.id)
        )
    ).all()
    actual_commands = sorted(
        (
            [
                command.simulation_time,
                code,
                command.desired_mode.value,
                command.desired_output_ratio,
                command.status.value,
                rule_name or MANUAL_REASON,
            ]
            for command, code, rule_name in command_rows
        ),
        key=_command_key,
    )
    command_mismatches: list[CommandMismatch] = []
    for index in range(max(len(expected_commands), len(actual_commands))):
        expected = expected_commands[index] if index < len(expected_commands) else None
        actual = actual_commands[index] if index < len(actual_commands) else None
        if expected is not None and actual is not None and _rows_equal(expected, actual):
            continue
        if len(command_mismatches) < MISMATCH_SAMPLE_LIMIT:
            command_mismatches.append(
                CommandMismatch(index=index, expected=expected, actual=actual)
            )
    commands_matched = not command_mismatches and len(expected_commands) == len(
        actual_commands
    )

    expected_version = replay_input.get("rule_set_version")
    rule_set_match = expected_version is None or expected_version == run.rule_set_version
    completed = t_now >= end - _TOLERANCE
    readings_ok = mismatched == 0 and missing == 0 and extra == 0

    return ReplayCompareOut(
        run_id=run.id,
        source_run_id=uuid.UUID(replay_input["source_run_id"]),
        status=run.status,
        checkpoint_time=float(replay_input["checkpoint_time"]),
        simulation_time_seconds=t_now,
        end_simulation_time=end,
        completed=completed,
        rule_set_version_expected=expected_version,
        rule_set_version_actual=run.rule_set_version,
        rule_set_match=rule_set_match,
        readings_expected=len(expected_readings),
        readings_actual=len(actual_readings),
        readings_matched=matched,
        readings_mismatched=mismatched,
        readings_missing=missing,
        readings_extra=extra,
        commands_expected=len(expected_commands),
        commands_actual=len(actual_commands),
        commands_matched=commands_matched,
        reproduced=completed and rule_set_match and readings_ok and commands_matched,
        reading_mismatches=mismatches,
        command_mismatches=command_mismatches,
    )
