"""
run / 이벤트 lineage 조회 (6단계 Day 23).

"run 부터 최종 이벤트까지" 를 DB 관계로 거슬러 올라간다.

  ControlEvent.command_id        → ControlCommand
  ControlCommand.rule_id/version → ControlRule (명령 당시 개정 번호는 command 에)
  ControlCommand.trigger_reading → SensorReading (판정 근거, dropout 이면 없음)
  command.simulation_time        → 같은 run 의 그 시각 이하 최신 WeatherSnapshot
  simulation_run_id              → SimulationRun (seed·모델·규칙 묶음 지문)
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Actuator,
    ControlCommand,
    ControlEvent,
    ControlRule,
    FaultInjection,
    Sensor,
    SensorReading,
    SimulationRun,
    WeatherSnapshot,
)
from app.domain.enums import ControlCommandStatus
from app.schemas.lineage import (
    EventLineageOut,
    LineageCommandOut,
    LineageEventOut,
    LineageReadingOut,
    LineageRuleOut,
    LineageRuleRef,
    LineageRunRef,
    LineageWeatherOut,
    RunLineageCounts,
    RunLineageOut,
)
from app.services.manual_control import MANUAL_REASON
from app.services.simulation import get_run_or_404


def _run_ref(run: SimulationRun) -> LineageRunRef:
    return LineageRunRef(
        id=run.id,
        name=run.name,
        status=run.status,
        random_seed=run.random_seed,
        weather_mode=run.weather_mode,
        environment_model_version=run.environment_model_version,
        rule_set_version=run.rule_set_version,
        simulation_time_seconds=run.simulation_time_seconds,
        replay_of_run_id=run.replay_of_run_id,
    )


async def _count(session: AsyncSession, statement) -> int:
    return int(await session.scalar(statement) or 0)


async def get_run_lineage(session: AsyncSession, run_id: uuid.UUID) -> RunLineageOut:
    run = await get_run_or_404(session, run_id)

    telemetry_versions = (
        await session.scalars(
            select(SensorReading.telemetry_schema_version)
            .where(SensorReading.simulation_run_id == run.id)
            .distinct()
        )
    ).all()
    sensor_versions = (
        await session.scalars(
            select(SensorReading.sensor_model_version)
            .where(SensorReading.simulation_run_id == run.id)
            .distinct()
        )
    ).all()

    command_counts = dict(
        (
            await session.execute(
                select(ControlCommand.rule_id, func.count())
                .where(
                    ControlCommand.simulation_run_id == run.id,
                    ControlCommand.rule_id.is_not(None),
                )
                .group_by(ControlCommand.rule_id)
            )
        ).all()
    )
    rules = (
        await session.scalars(
            select(ControlRule)
            .where(ControlRule.room_id == run.room_id)
            .order_by(ControlRule.priority, ControlRule.name)
        )
    ).all()

    command_filter = ControlCommand.simulation_run_id == run.id
    counts = RunLineageCounts(
        readings=await _count(
            session,
            select(func.count())
            .select_from(SensorReading)
            .where(SensorReading.simulation_run_id == run.id),
        ),
        weather_snapshots=await _count(
            session,
            select(func.count())
            .select_from(WeatherSnapshot)
            .where(WeatherSnapshot.simulation_run_id == run.id),
        ),
        rule_commands=await _count(
            session,
            select(func.count())
            .select_from(ControlCommand)
            .where(
                command_filter,
                ControlCommand.rule_id.is_not(None),
                ControlCommand.status != ControlCommandStatus.CANCELLED,
            ),
        ),
        manual_commands=await _count(
            session,
            select(func.count())
            .select_from(ControlCommand)
            .where(command_filter, ControlCommand.reason == MANUAL_REASON),
        ),
        blocked_commands=await _count(
            session,
            select(func.count())
            .select_from(ControlCommand)
            .where(command_filter, ControlCommand.status == ControlCommandStatus.CANCELLED),
        ),
        events=await _count(
            session,
            select(func.count())
            .select_from(ControlEvent)
            .where(ControlEvent.simulation_run_id == run.id),
        ),
        faults=await _count(
            session,
            select(func.count())
            .select_from(FaultInjection)
            .where(FaultInjection.simulation_run_id == run.id),
        ),
    )

    replay_of = (
        await session.get(SimulationRun, run.replay_of_run_id)
        if run.replay_of_run_id is not None
        else None
    )
    replays = (
        await session.scalars(
            select(SimulationRun)
            .where(SimulationRun.replay_of_run_id == run.id)
            .order_by(SimulationRun.created_at.desc())
        )
    ).all()

    return RunLineageOut(
        run=_run_ref(run),
        started_at=run.started_at,
        ended_at=run.ended_at,
        checkpoint_time=(
            float(run.initial_state.get("simulation_time") or 0.0)
            if run.initial_state is not None
            else None
        ),
        telemetry_schema_versions=sorted(telemetry_versions),
        sensor_model_versions=sorted(sensor_versions),
        rules=[
            LineageRuleOut(
                id=rule.id,
                name=rule.name,
                version=rule.version,
                enabled=rule.enabled,
                metric=rule.metric.value,
                target_actuator_type=rule.target_actuator_type.value,
                command_count=int(command_counts.get(rule.id, 0)),
            )
            for rule in rules
        ],
        counts=counts,
        replay_of=_run_ref(replay_of) if replay_of is not None else None,
        replays=[_run_ref(item) for item in replays],
    )


async def get_event_lineage(session: AsyncSession, event_id: uuid.UUID) -> EventLineageOut:
    event = await session.get(ControlEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="control event not found")
    command = await session.get(ControlCommand, event.command_id)
    assert command is not None
    actuator = await session.get(Actuator, command.actuator_id)
    assert actuator is not None
    run = await get_run_or_404(session, event.simulation_run_id)

    rule_ref: LineageRuleRef | None = None
    if command.rule_id is not None:
        rule = await session.get(ControlRule, command.rule_id)
        if rule is not None:
            rule_ref = LineageRuleRef(
                id=rule.id,
                name=rule.name,
                version_at_command=command.rule_version,
                current_version=rule.version,
                metric=rule.metric.value,
                comparator=rule.comparator.value,
                start_threshold=rule.start_threshold,
                stop_threshold=rule.stop_threshold,
            )

    reading_out: LineageReadingOut | None = None
    if command.trigger_reading_id is not None:
        row = (
            await session.execute(
                select(SensorReading, Sensor)
                .join(Sensor, SensorReading.sensor_id == Sensor.id)
                .where(SensorReading.id == command.trigger_reading_id)
            )
        ).first()
        if row is not None:
            reading, sensor = row
            reading_out = LineageReadingOut(
                id=reading.id,
                sensor_code=sensor.code,
                sensor_type=sensor.sensor_type.value,
                source_sequence=reading.source_sequence,
                simulation_time=reading.simulation_time,
                raw_value=reading.raw_value,
                value=reading.value,
                quality=reading.quality.value,
                quality_reason=reading.quality_reason,
                telemetry_schema_version=reading.telemetry_schema_version,
                sensor_model_version=reading.sensor_model_version,
            )

    snapshot = await session.scalar(
        select(WeatherSnapshot)
        .where(
            WeatherSnapshot.simulation_run_id == run.id,
            WeatherSnapshot.simulation_time <= command.simulation_time,
        )
        .order_by(WeatherSnapshot.simulation_time.desc())
        .limit(1)
    )

    return EventLineageOut(
        event=LineageEventOut(
            id=event.id,
            event_type=event.event_type.value,
            message=event.message,
            actual_output_ratio=event.actual_output_ratio,
            simulation_time=event.simulation_time,
            recorded_at=event.recorded_at,
        ),
        command=LineageCommandOut(
            id=command.id,
            origin="rule" if command.rule_id is not None else MANUAL_REASON,
            status=command.status.value,
            reason=command.reason,
            desired_mode=command.desired_mode.value,
            desired_output_ratio=command.desired_output_ratio,
            simulation_time=command.simulation_time,
            idempotency_key=command.idempotency_key,
            actuator_code=actuator.code,
            actuator_type=actuator.actuator_type.value,
        ),
        rule=rule_ref,
        trigger_reading=reading_out,
        weather=(
            LineageWeatherOut(
                sequence=snapshot.sequence,
                source=snapshot.source,
                simulation_time=snapshot.simulation_time,
                outdoor_temperature_c=snapshot.outdoor_temperature_c,
                outdoor_humidity_pct=snapshot.outdoor_humidity_pct,
            )
            if snapshot is not None
            else None
        ),
        run=_run_ref(run),
    )
