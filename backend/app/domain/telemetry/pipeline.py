"""
Telemetry ingest 파이프라인 (6단계 Day 20).

TelemetryReadingIn → 단위 정규화 → 범위 quality → TelemetryReadingNormalized
"""

from __future__ import annotations

from app.domain.telemetry.normalize import (
    UnitNormalizationError,
    apply_range_quality,
    normalize_unit_value,
)
from app.domain.telemetry.schema import (
    TELEMETRY_READING_SCHEMA_VERSION,
    TelemetryReadingIn,
    TelemetryReadingNormalized,
)


def process_telemetry_reading(
    reading: TelemetryReadingIn,
) -> TelemetryReadingNormalized:
    """
    입력 계약을 검증한 뒤 raw 를 보존하고 normalized/quality 를 붙인다.

    Raises
    ------
    UnitNormalizationError
        센서 타입과 호환되지 않는 input_unit
    """
    if reading.schema_version != TELEMETRY_READING_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported telemetry schema_version={reading.schema_version!r}"
        )

    try:
        converted, unit = normalize_unit_value(
            sensor_type=reading.sensor_type,
            raw_value=reading.raw_value,
            input_unit=reading.input_unit,
        )
    except UnitNormalizationError:
        raise

    stored, quality, reason = apply_range_quality(
        sensor_type=reading.sensor_type,
        normalized_value=converted,
    )

    return TelemetryReadingNormalized(
        schema_version=TELEMETRY_READING_SCHEMA_VERSION,
        sensor_type=reading.sensor_type,
        raw_value=reading.raw_value,
        input_unit=reading.input_unit,
        normalized_value=stored,
        unit=unit,
        quality=quality,
        quality_reason=reason,
        source=reading.source,
        simulation_time=reading.simulation_time,
        sampled_at=reading.sampled_at,
        sensor_id=reading.sensor_id,
        farm_id=reading.farm_id,
        room_id=reading.room_id,
        simulation_run_id=reading.simulation_run_id,
        sensor_model_version=reading.sensor_model_version,
    )


__all__ = [
    "UnitNormalizationError",
    "process_telemetry_reading",
]
