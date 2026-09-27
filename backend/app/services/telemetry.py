"""
센서 reading 적재·품질 조회 서비스 (6단계 Day 21).

=============================================================================
경로
-----------------------------------------------------------------------------
시뮬 step (services.simulation) 과 외부 ingest (POST /simulations/{id}/readings)
가 **같은** 판정·적재 경로를 탄다.

  DB 에서 센서별 StreamState 복원
  → StreamQualityAssessor.assess (sequence·시간역전·변화율·지연)
  → ReadingWriter 가 누락 마커 + reading 을 append-only 로 추가

조회: get_sensor_health 가 센서별 최신 행에 stale/missing 을 덧씌운다.
"""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Room, Sensor, SensorReading, SimulationRun
from app.domain.enums import (
    ReadingQuality,
    ReadingSource,
    SimulationStatus,
    Unit,
)
from app.domain.telemetry import (
    DEFAULT_QUALITY_CONFIG,
    TELEMETRY_READING_SCHEMA_VERSION,
    LatestReadingView,
    QualityConfig,
    StreamAssessment,
    StreamQualityAssessor,
    StreamState,
    UnitNormalizationError,
    assess_sensor_health,
    process_telemetry_reading,
)
from app.schemas.telemetry import (
    IngestRejection,
    SensorHealthOut,
    SensorHealthReport,
    TelemetryIngestRequest,
    TelemetryIngestResult,
)

_ALLOWED_INGEST = {SimulationStatus.RUNNING, SimulationStatus.PAUSED}


# ---------------------------------------------------------------------------
# 상태 복원
# ---------------------------------------------------------------------------


async def next_run_sequence(session: AsyncSession, run_id: uuid.UUID) -> int:
    """run 적재 순서 다음 값. UNIQUE(simulation_run_id, sequence) 유지용."""
    current = await session.scalar(
        select(func.coalesce(func.max(SensorReading.sequence), -1)).where(
            SensorReading.simulation_run_id == run_id
        )
    )
    return int(current) + 1


async def _load_flat_runs(
    session: AsyncSession,
    run_id: uuid.UUID,
    window: int,
) -> dict[uuid.UUID, tuple[float, int]]:
    """센서별 (최신 raw, 최신부터 같은 raw 연속 횟수). 최근 window 행만 본다."""
    row_number = (
        func.row_number()
        .over(
            partition_by=SensorReading.sensor_id,
            order_by=SensorReading.sequence.desc(),
        )
        .label("rn")
    )
    recent = (
        select(SensorReading.sensor_id, SensorReading.raw_value, row_number)
        .where(
            SensorReading.simulation_run_id == run_id,
            SensorReading.raw_value.is_not(None),
        )
        .subquery()
    )
    rows = await session.execute(
        select(recent.c.sensor_id, recent.c.raw_value)
        .where(recent.c.rn <= window)
        .order_by(recent.c.sensor_id, recent.c.rn)
    )
    runs: dict[uuid.UUID, tuple[float, int]] = {}
    broken: set[uuid.UUID] = set()
    for sensor_id, raw in rows.all():
        if sensor_id in broken:
            continue
        current = runs.get(sensor_id)
        if current is None:
            runs[sensor_id] = (raw, 1)
        elif raw == current[0]:
            runs[sensor_id] = (current[0], current[1] + 1)
        else:
            broken.add(sensor_id)
    return runs


async def load_stream_states(
    session: AsyncSession,
    run_id: uuid.UUID,
    config: QualityConfig = DEFAULT_QUALITY_CONFIG,
) -> dict[uuid.UUID, StreamState]:
    """
    센서별 수신측 기준 상태를 DB 에서 복원한다.

    - last_sequence: 누락 마커 포함 최대 source_sequence
    - last_value / last_simulation_time: BAD·누락이 아닌 최신 행
    - last_raw / flat_run: 최근 원시값 연속 (stuck 검출용)
    """
    max_rows = await session.execute(
        select(SensorReading.sensor_id, func.max(SensorReading.source_sequence))
        .where(SensorReading.simulation_run_id == run_id)
        .group_by(SensorReading.sensor_id)
    )
    last_sequences = {sensor_id: seq for sensor_id, seq in max_rows.all()}

    baselines = (
        await session.scalars(
            select(SensorReading)
            .where(
                SensorReading.simulation_run_id == run_id,
                SensorReading.quality.not_in([ReadingQuality.BAD, ReadingQuality.MISSING]),
                SensorReading.value.is_not(None),
            )
            .distinct(SensorReading.sensor_id)
            .order_by(SensorReading.sensor_id, SensorReading.sequence.desc())
        )
    ).all()
    baseline_by_sensor = {row.sensor_id: row for row in baselines}
    flat_runs = await _load_flat_runs(session, run_id, config.flatline_samples)

    states: dict[uuid.UUID, StreamState] = {}
    for sensor_id in set(last_sequences) | set(baseline_by_sensor):
        baseline = baseline_by_sensor.get(sensor_id)
        last_raw, flat_run = flat_runs.get(sensor_id, (None, 0))
        states[sensor_id] = StreamState(
            last_sequence=last_sequences.get(sensor_id),
            last_value=baseline.value if baseline else None,
            last_simulation_time=baseline.simulation_time if baseline else None,
            last_raw=last_raw,
            flat_run=flat_run,
        )
    return states


# ---------------------------------------------------------------------------
# 적재
# ---------------------------------------------------------------------------


@dataclass
class ReadingWriter:
    """
    판정 결과를 sensor_readings 행으로 추가한다 (commit 은 호출자).

    run 적재 순서(sequence)를 여기서 발급해 마커와 reading 이 번호를 공유한다.
    """

    session: AsyncSession
    run: SimulationRun
    next_sequence: int
    # 마지막으로 추가한 reading 행 id — 규칙 명령의 판정 근거(trigger_reading_id)
    last_reading_id: uuid.UUID | None = None

    def _issue_sequence(self) -> int:
        value = self.next_sequence
        self.next_sequence += 1
        return value

    def add(
        self,
        *,
        sensor: Sensor,
        assessment: StreamAssessment,
        source_sequence: int,
        value: float,
        raw_value: float,
        unit: Unit,
        input_unit: Unit,
        source: ReadingSource,
        simulation_time: float,
        sampled_at: datetime,
        ingested_at: datetime,
        telemetry_schema_version: str = TELEMETRY_READING_SCHEMA_VERSION,
    ) -> int:
        """누락 마커 + reading 을 추가하고 추가한 행 수를 돌려준다."""
        verdict = assessment.verdict
        if verdict is None:
            return 0

        # 누락 마커는 측정 시각을 모르므로 sampled_at 에 검출 시각을 쓴다.
        for marker in assessment.missing_markers:
            self.session.add(
                SensorReading(
                    sensor_id=sensor.id,
                    farm_id=self.run.farm_id,
                    room_id=self.run.room_id,
                    simulation_run_id=self.run.id,
                    sequence=self._issue_sequence(),
                    source_sequence=marker.source_sequence,
                    value=None,
                    raw_value=None,
                    unit=sensor.unit,
                    input_unit=sensor.unit,
                    quality=ReadingQuality.MISSING,
                    quality_reason=marker.reason,
                    telemetry_schema_version=telemetry_schema_version,
                    source=source,
                    sensor_model_version=sensor.model_version,
                    simulation_time=marker.simulation_time,
                    sampled_at=ingested_at,
                    ingested_at=ingested_at,
                )
            )

        self.last_reading_id = uuid.uuid4()
        self.session.add(
            SensorReading(
                id=self.last_reading_id,
                sensor_id=sensor.id,
                farm_id=self.run.farm_id,
                room_id=self.run.room_id,
                simulation_run_id=self.run.id,
                sequence=self._issue_sequence(),
                source_sequence=source_sequence,
                value=value,
                raw_value=raw_value,
                unit=unit,
                input_unit=input_unit,
                quality=verdict.quality,
                quality_reason=verdict.reason_text,
                telemetry_schema_version=telemetry_schema_version,
                source=source,
                sensor_model_version=sensor.model_version,
                simulation_time=simulation_time,
                sampled_at=sampled_at,
                ingested_at=ingested_at,
            )
        )
        return len(assessment.missing_markers) + 1


async def open_stream(
    session: AsyncSession,
    run: SimulationRun,
    config: QualityConfig = DEFAULT_QUALITY_CONFIG,
    *,
    seed_states: Mapping[uuid.UUID, StreamState] | None = None,
) -> tuple[StreamQualityAssessor, ReadingWriter]:
    """
    run 의 판정기·적재기를 DB 상태에서 이어 받는다.

    seed_states: 이 run 에 아직 행이 없는 센서의 출발 상태 (재생 run 의 체크포인트).
    DB 에 행이 생긴 센서는 DB 가 우선한다.
    """
    states = dict(seed_states or {})
    states.update(await load_stream_states(session, run.id, config))
    assessor = StreamQualityAssessor(config=config, states=states)
    writer = ReadingWriter(
        session=session,
        run=run,
        next_sequence=await next_run_sequence(session, run.id),
    )
    return assessor, writer


# ---------------------------------------------------------------------------
# 외부 ingest
# ---------------------------------------------------------------------------


async def ingest_readings(
    session: AsyncSession,
    run_id: uuid.UUID,
    request: TelemetryIngestRequest,
) -> TelemetryIngestResult:
    """
    외부 reading 배치를 판정·적재한다.

    거부(중복·역순·단위·알 수 없는 센서)된 건은 저장하지 않고 사유만 돌려준다.
    나머지는 한 트랜잭션으로 commit 한다.
    """
    run = await session.get(SimulationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="simulation run not found")
    if run.status not in _ALLOWED_INGEST:
        raise HTTPException(
            status_code=409,
            detail=f"cannot ingest readings for status={run.status.value}",
        )

    sensors = (
        await session.scalars(select(Sensor).where(Sensor.room_id == run.room_id))
    ).all()
    sensors_by_id = {sensor.id: sensor for sensor in sensors}
    sensors_by_type = {sensor.sensor_type: sensor for sensor in sensors}

    assessor, writer = await open_stream(session, run)
    now = datetime.now(UTC)
    rejected: list[IngestRejection] = []
    counts: Counter[ReadingQuality] = Counter()
    accepted = 0
    missing_markers = 0
    missing_truncated = 0

    def reject(index: int, reading, reason: str) -> None:
        rejected.append(
            IngestRejection(
                index=index,
                sensor_type=reading.sensor_type,
                sequence=reading.sequence,
                reason=reason,
            )
        )

    for index, reading in enumerate(request.readings):
        if reading.simulation_run_id is not None and reading.simulation_run_id != run.id:
            reject(index, reading, "run_mismatch")
            continue
        if reading.sensor_id is not None:
            sensor = sensors_by_id.get(reading.sensor_id)
            if sensor is not None and sensor.sensor_type is not reading.sensor_type:
                reject(index, reading, "sensor_type_mismatch")
                continue
        else:
            sensor = sensors_by_type.get(reading.sensor_type)
        if sensor is None:
            reject(index, reading, "unknown_sensor")
            continue
        if reading.sequence is None:
            reject(index, reading, "sequence_required")
            continue
        try:
            normalized = process_telemetry_reading(reading)
        except UnitNormalizationError:
            reject(index, reading, "unit_incompatible")
            continue

        sampled_at = reading.sampled_at or now
        assessment = assessor.assess(
            sensor.id,
            sensor_type=sensor.sensor_type,
            source_sequence=reading.sequence,
            value=normalized.normalized_value,
            simulation_time=normalized.simulation_time,
            base_quality=normalized.quality,
            base_reason=normalized.quality_reason,
            raw_value=normalized.raw_value,
            sampled_at=sampled_at,
            ingested_at=now,
        )
        if not assessment.accepted:
            reject(index, reading, assessment.reject_reason or "rejected")
            continue

        writer.add(
            sensor=sensor,
            assessment=assessment,
            source_sequence=reading.sequence,
            value=normalized.normalized_value,
            raw_value=normalized.raw_value,
            unit=normalized.unit,
            input_unit=normalized.input_unit,
            source=normalized.source,
            simulation_time=normalized.simulation_time,
            sampled_at=sampled_at,
            ingested_at=now,
        )
        accepted += 1
        missing_markers += len(assessment.missing_markers)
        missing_truncated += assessment.missing_truncated
        counts[assessment.verdict.quality] += 1
        counts[ReadingQuality.MISSING] += len(assessment.missing_markers)

    try:
        await session.commit()
    except IntegrityError as exc:
        # 동시에 같은 스트림을 적재하면 source_sequence UNIQUE 에 걸린다
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="concurrent ingest conflict on sensor sequence; retry",
        ) from exc

    return TelemetryIngestResult(
        run_id=run.id,
        accepted=accepted,
        missing_markers=missing_markers,
        missing_truncated=missing_truncated,
        rejected=rejected,
        quality_counts=dict(counts),
    )


# ---------------------------------------------------------------------------
# 센서 품질 조회
# ---------------------------------------------------------------------------


async def latest_run_for_farm(
    session: AsyncSession,
    farm_id: uuid.UUID,
) -> SimulationRun | None:
    return await session.scalar(
        select(SimulationRun)
        .where(SimulationRun.farm_id == farm_id)
        .order_by(SimulationRun.created_at.desc())
        .limit(1)
    )


async def get_sensor_health(
    session: AsyncSession,
    farm_id: uuid.UUID,
    *,
    recent_window: int = 60,
    config: QualityConfig = DEFAULT_QUALITY_CONFIG,
) -> SensorHealthReport:
    """
    최신 run 기준 센서별 현재 품질.

    - 최신 행: run 적재 순서(sequence) 기준
    - recent_counts: 센서별 최근 recent_window 행의 품질 분포
    """
    from app.services.farm import get_farm_or_404

    await get_farm_or_404(session, farm_id)
    room = await session.scalar(select(Room).where(Room.farm_id == farm_id).limit(1))
    if room is None:
        raise HTTPException(status_code=404, detail="room not found for farm")

    sensors = (
        await session.scalars(
            select(Sensor).where(Sensor.room_id == room.id).order_by(Sensor.code)
        )
    ).all()
    run = await latest_run_for_farm(session, farm_id)
    now = datetime.now(UTC)

    latest_by_sensor: dict[uuid.UUID, SensorReading] = {}
    last_valued_by_sensor: dict[uuid.UUID, SensorReading] = {}
    counts_by_sensor: dict[uuid.UUID, Counter[ReadingQuality]] = {}

    if run is not None:
        latest_rows = (
            await session.scalars(
                select(SensorReading)
                .where(SensorReading.simulation_run_id == run.id)
                .distinct(SensorReading.sensor_id)
                .order_by(SensorReading.sensor_id, SensorReading.sequence.desc())
            )
        ).all()
        latest_by_sensor = {row.sensor_id: row for row in latest_rows}

        missing_latest = [
            sensor_id
            for sensor_id, row in latest_by_sensor.items()
            if row.value is None
        ]
        if missing_latest:
            valued_rows = (
                await session.scalars(
                    select(SensorReading)
                    .where(
                        SensorReading.simulation_run_id == run.id,
                        SensorReading.sensor_id.in_(missing_latest),
                        SensorReading.value.is_not(None),
                    )
                    .distinct(SensorReading.sensor_id)
                    .order_by(SensorReading.sensor_id, SensorReading.sequence.desc())
                )
            ).all()
            last_valued_by_sensor = {row.sensor_id: row for row in valued_rows}

        row_number = (
            func.row_number()
            .over(
                partition_by=SensorReading.sensor_id,
                order_by=SensorReading.sequence.desc(),
            )
            .label("rn")
        )
        recent = (
            select(SensorReading.sensor_id, SensorReading.quality, row_number)
            .where(SensorReading.simulation_run_id == run.id)
            .subquery()
        )
        count_rows = await session.execute(
            select(recent.c.sensor_id, recent.c.quality, func.count())
            .where(recent.c.rn <= recent_window)
            .group_by(recent.c.sensor_id, recent.c.quality)
        )
        for sensor_id, quality, count in count_rows.all():
            counts_by_sensor.setdefault(sensor_id, Counter())[ReadingQuality(quality)] = count

    run_running = run is not None and run.status is SimulationStatus.RUNNING
    current_t = run.simulation_time_seconds if run is not None else None
    summary: Counter[ReadingQuality] = Counter()
    out: list[SensorHealthOut] = []

    for sensor in sensors:
        latest = latest_by_sensor.get(sensor.id)
        verdict = assess_sensor_health(
            (
                LatestReadingView(
                    quality=latest.quality,
                    quality_reason=latest.quality_reason,
                    simulation_time=latest.simulation_time,
                    ingested_at=latest.ingested_at,
                )
                if latest is not None
                else None
            ),
            current_simulation_time=current_t,
            now=now,
            run_running=run_running,
            config=config,
        )
        summary[verdict.quality] += 1
        valued = latest if latest is not None and latest.value is not None else (
            last_valued_by_sensor.get(sensor.id)
        )
        out.append(
            SensorHealthOut(
                sensor_id=sensor.id,
                code=sensor.code,
                name=sensor.name,
                sensor_type=sensor.sensor_type,
                unit=sensor.unit,
                quality=verdict.quality,
                quality_reason=verdict.reason,
                stored_quality=latest.quality if latest is not None else None,
                value=valued.value if valued is not None else None,
                raw_value=valued.raw_value if valued is not None else None,
                source_sequence=latest.source_sequence if latest is not None else None,
                simulation_time=latest.simulation_time if latest is not None else None,
                ingested_at=latest.ingested_at if latest is not None else None,
                age_simulation_s=verdict.age_simulation_s,
                age_wall_s=verdict.age_wall_s,
                recent_counts=dict(counts_by_sensor.get(sensor.id, Counter())),
            )
        )

    return SensorHealthReport(
        farm_id=farm_id,
        run_id=run.id if run is not None else None,
        run_status=run.status if run is not None else None,
        current_simulation_time=current_t,
        generated_at=now,
        recent_window=recent_window,
        stale_after_simulation_s=config.stale_after_simulation_s,
        stale_ingest_wall_s=config.stale_ingest_wall_s,
        summary=dict(summary),
        sensors=out,
    )
