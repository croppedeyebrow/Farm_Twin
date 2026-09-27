"""
측정 이력·1분/5분 집계·품질 리포트 (6단계 Day 23).

원시 sensor_readings 는 append-only 그대로 두고 조회 시점에 집계한다.
집계 기준은 가상 시계(simulation_time) — wall-clock 은 스텝 배치 속도에 따라
몰려 찍히므로 시계열 의미가 없다.

  bucket = floor(simulation_time / bucket_seconds) * bucket_seconds
  avg/min/max : quality=good 행만
  quality_counts : 모든 품질 (누락 마커 포함)
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import case, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FaultInjection, Sensor, SensorReading, SimulationRun
from app.domain.enums import ReadingQuality
from app.schemas.history import (
    FaultEpisode,
    HistoryPoint,
    HistorySeries,
    QualityReportOut,
    ReadingHistoryOut,
    ReasonCount,
    SensorQualityReport,
)
from app.services.farm import get_farm_or_404
from app.services.simulation import get_run_or_404
from app.services.telemetry import latest_run_for_farm

ALLOWED_BUCKETS = (0, 60, 300)
MAX_POINTS = 2000
TOP_REASONS = 3


def _empty_counts() -> dict[ReadingQuality, int]:
    return {quality: 0 for quality in ReadingQuality}


async def _room_sensors(
    session: AsyncSession,
    run: SimulationRun,
    sensor_code: str | None,
) -> list[Sensor]:
    statement = select(Sensor).where(Sensor.room_id == run.room_id).order_by(Sensor.code)
    if sensor_code is not None:
        statement = statement.where(Sensor.code == sensor_code)
    sensors = list((await session.scalars(statement)).all())
    if sensor_code is not None and not sensors:
        raise HTTPException(status_code=404, detail=f"sensor {sensor_code} not found in run room")
    return sensors


async def _raw_points(
    session: AsyncSession,
    run_id: uuid.UUID,
    sensor: Sensor,
    *,
    start: float | None,
    end: float | None,
    limit: int,
) -> list[HistoryPoint]:
    statement = select(SensorReading).where(
        SensorReading.simulation_run_id == run_id,
        SensorReading.sensor_id == sensor.id,
    )
    if start is not None:
        statement = statement.where(SensorReading.simulation_time >= start)
    if end is not None:
        statement = statement.where(SensorReading.simulation_time <= end)
    rows = (
        await session.scalars(statement.order_by(SensorReading.sequence.desc()).limit(limit))
    ).all()
    points: list[HistoryPoint] = []
    for row in reversed(rows):
        counts = _empty_counts()
        counts[row.quality] = 1
        points.append(
            HistoryPoint(
                t=row.simulation_time,
                count=1,
                avg=row.value,
                min=row.value,
                max=row.value,
                quality_counts=counts,
                raw_value=row.raw_value,
                quality=row.quality,
                quality_reason=row.quality_reason,
                source_sequence=row.source_sequence,
            )
        )
    return points


async def _bucket_points(
    session: AsyncSession,
    run_id: uuid.UUID,
    sensor: Sensor,
    *,
    bucket_seconds: int,
    start: float | None,
    end: float | None,
    limit: int,
) -> list[HistoryPoint]:
    # 바인드 파라미터면 SELECT·GROUP BY 식이 서로 달라져 PG 가 거부한다
    width = literal_column(str(int(bucket_seconds)))
    bucket = (func.floor(SensorReading.simulation_time / width) * width).label("bucket")
    good_value = case(
        (SensorReading.quality == ReadingQuality.GOOD, SensorReading.value),
        else_=None,
    )
    statement = select(
        bucket,
        func.count(),
        func.avg(good_value),
        func.min(good_value),
        func.max(good_value),
        *(
            func.count().filter(SensorReading.quality == quality)
            for quality in ReadingQuality
        ),
    ).where(
        SensorReading.simulation_run_id == run_id,
        SensorReading.sensor_id == sensor.id,
    )
    if start is not None:
        statement = statement.where(SensorReading.simulation_time >= start)
    if end is not None:
        statement = statement.where(SensorReading.simulation_time <= end)
    rows = (
        await session.execute(
            statement.group_by(bucket).order_by(bucket.desc()).limit(limit)
        )
    ).all()
    points: list[HistoryPoint] = []
    for row in reversed(rows):
        t, count, avg, low, high, *quality_counts = row
        points.append(
            HistoryPoint(
                t=float(t),
                count=int(count),
                avg=float(avg) if avg is not None else None,
                min=float(low) if low is not None else None,
                max=float(high) if high is not None else None,
                quality_counts={
                    quality: int(value)
                    for quality, value in zip(ReadingQuality, quality_counts, strict=True)
                },
            )
        )
    return points


async def reading_history(
    session: AsyncSession,
    run: SimulationRun | None,
    *,
    sensor_code: str | None = None,
    bucket_seconds: int = 60,
    start: float | None = None,
    end: float | None = None,
    limit: int = 240,
) -> ReadingHistoryOut:
    if bucket_seconds not in ALLOWED_BUCKETS:
        raise HTTPException(
            status_code=422,
            detail=f"bucket_seconds must be one of {ALLOWED_BUCKETS}",
        )
    limit = max(1, min(limit, MAX_POINTS))
    if run is None:
        return ReadingHistoryOut(
            run_id=None,
            bucket_seconds=bucket_seconds,
            start_simulation_time=start,
            end_simulation_time=end,
            series=[],
        )

    series: list[HistorySeries] = []
    for sensor in await _room_sensors(session, run, sensor_code):
        if bucket_seconds == 0:
            points = await _raw_points(
                session, run.id, sensor, start=start, end=end, limit=limit
            )
        else:
            points = await _bucket_points(
                session,
                run.id,
                sensor,
                bucket_seconds=bucket_seconds,
                start=start,
                end=end,
                limit=limit,
            )
        series.append(
            HistorySeries(
                sensor_id=sensor.id,
                sensor_code=sensor.code,
                sensor_type=sensor.sensor_type,
                unit=sensor.unit,
                points=points,
            )
        )
    return ReadingHistoryOut(
        run_id=run.id,
        bucket_seconds=bucket_seconds,
        start_simulation_time=start,
        end_simulation_time=end,
        series=series,
    )


async def run_reading_history(
    session: AsyncSession,
    run_id: uuid.UUID,
    **kwargs,
) -> ReadingHistoryOut:
    return await reading_history(session, await get_run_or_404(session, run_id), **kwargs)


async def farm_reading_history(
    session: AsyncSession,
    farm_id: uuid.UUID,
    **kwargs,
) -> ReadingHistoryOut:
    await get_farm_or_404(session, farm_id)
    return await reading_history(session, await latest_run_for_farm(session, farm_id), **kwargs)


# ---------------------------------------------------------------------------
# 품질 리포트
# ---------------------------------------------------------------------------


def _ratio(part: int, total: int) -> float | None:
    return part / total if total else None


async def quality_report(
    session: AsyncSession,
    run: SimulationRun | None,
) -> QualityReportOut:
    now = datetime.now(UTC)
    if run is None:
        return QualityReportOut(
            run_id=None,
            run_status=None,
            generated_at=now,
            total=0,
            quality_counts=_empty_counts(),
            good_ratio=None,
            sensors=[],
        )

    sensors = (
        await session.scalars(
            select(Sensor).where(Sensor.room_id == run.room_id).order_by(Sensor.code)
        )
    ).all()

    count_rows = (
        await session.execute(
            select(
                SensorReading.sensor_id,
                SensorReading.quality,
                func.count(),
                func.min(SensorReading.simulation_time),
                func.max(SensorReading.simulation_time),
            )
            .where(SensorReading.simulation_run_id == run.id)
            .group_by(SensorReading.sensor_id, SensorReading.quality)
        )
    ).all()
    reason_rows = (
        await session.execute(
            select(SensorReading.sensor_id, SensorReading.quality_reason, func.count())
            .where(
                SensorReading.simulation_run_id == run.id,
                SensorReading.quality != ReadingQuality.GOOD,
                SensorReading.quality_reason.is_not(None),
            )
            .group_by(SensorReading.sensor_id, SensorReading.quality_reason)
        )
    ).all()
    fault_rows = (
        await session.scalars(
            select(FaultInjection)
            .where(FaultInjection.simulation_run_id == run.id)
            .order_by(FaultInjection.start_simulation_time)
        )
    ).all()

    counts_by_sensor: dict[uuid.UUID, dict[ReadingQuality, int]] = {}
    span_by_sensor: dict[uuid.UUID, tuple[float, float]] = {}
    for sensor_id, quality, count, first_t, last_t in count_rows:
        counts_by_sensor.setdefault(sensor_id, _empty_counts())[quality] = int(count)
        prev = span_by_sensor.get(sensor_id)
        span_by_sensor[sensor_id] = (
            (min(prev[0], first_t), max(prev[1], last_t)) if prev else (first_t, last_t)
        )
    reasons_by_sensor: dict[uuid.UUID, Counter[str]] = {}
    for sensor_id, reason, count in reason_rows:
        reasons_by_sensor.setdefault(sensor_id, Counter())[reason] += int(count)

    overall = _empty_counts()
    reports: list[SensorQualityReport] = []
    for sensor in sensors:
        counts = counts_by_sensor.get(sensor.id, _empty_counts())
        total = sum(counts.values())
        for quality, value in counts.items():
            overall[quality] += value
        span = span_by_sensor.get(sensor.id)
        reports.append(
            SensorQualityReport(
                sensor_id=sensor.id,
                sensor_code=sensor.code,
                sensor_type=sensor.sensor_type,
                total=total,
                quality_counts=counts,
                good_ratio=_ratio(counts[ReadingQuality.GOOD], total),
                missing_ratio=_ratio(counts[ReadingQuality.MISSING], total),
                first_simulation_time=span[0] if span else None,
                last_simulation_time=span[1] if span else None,
                top_reasons=[
                    ReasonCount(reason=reason, count=count)
                    for reason, count in reasons_by_sensor.get(
                        sensor.id, Counter()
                    ).most_common(TOP_REASONS)
                ],
                faults=[
                    FaultEpisode(
                        fault_type=fault.fault_type.value,
                        start_simulation_time=fault.start_simulation_time,
                        end_simulation_time=fault.end_simulation_time,
                    )
                    for fault in fault_rows
                    if fault.sensor_id == sensor.id
                ],
            )
        )

    grand_total = sum(overall.values())
    return QualityReportOut(
        run_id=run.id,
        run_status=run.status,
        generated_at=now,
        total=grand_total,
        quality_counts=overall,
        good_ratio=_ratio(overall[ReadingQuality.GOOD], grand_total),
        sensors=reports,
    )


async def run_quality_report(session: AsyncSession, run_id: uuid.UUID) -> QualityReportOut:
    return await quality_report(session, await get_run_or_404(session, run_id))


async def farm_quality_report(session: AsyncSession, farm_id: uuid.UUID) -> QualityReportOut:
    await get_farm_or_404(session, farm_id)
    return await quality_report(session, await latest_run_for_farm(session, farm_id))
