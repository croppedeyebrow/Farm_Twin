"""
6단계 Day 20 — telemetry reading 계약·단위 정규화·raw/normalized/quality.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.enums import ReadingQuality, ReadingSource, SensorType, Unit
from app.domain.telemetry import (
    TELEMETRY_READING_SCHEMA_VERSION,
    TelemetryReadingIn,
    UnitNormalizationError,
    process_telemetry_reading,
)


def _reading(**overrides: object) -> TelemetryReadingIn:
    data: dict[str, object] = {
        "sensor_type": SensorType.TEMPERATURE,
        "raw_value": 77.0,
        "input_unit": Unit.FAHRENHEIT,
        "source": ReadingSource.SIMULATED,
        "simulation_time": 60.0,
    }
    data.update(overrides)
    return TelemetryReadingIn.model_validate(data)


def test_schema_version_is_telemetry_reading_v1() -> None:
    reading = _reading()
    assert reading.schema_version == TELEMETRY_READING_SCHEMA_VERSION
    assert reading.schema_version == "telemetry.reading.v1"


def test_rejects_unknown_schema_version() -> None:
    with pytest.raises(ValidationError):
        TelemetryReadingIn.model_validate(
            {
                "schema_version": "telemetry.reading.v0",
                "sensor_type": SensorType.TEMPERATURE,
                "raw_value": 20.0,
                "input_unit": Unit.CELSIUS,
                "simulation_time": 0.0,
            }
        )


def test_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        TelemetryReadingIn.model_validate(
            {
                "sensor_type": SensorType.TEMPERATURE,
                "raw_value": 20.0,
                "input_unit": Unit.CELSIUS,
                "simulation_time": 0.0,
                "normalized_value": 20.0,  # ingest 에 넣으면 안 됨
            }
        )


def test_fahrenheit_normalizes_to_celsius() -> None:
    out = process_telemetry_reading(_reading(raw_value=77.0, input_unit=Unit.FAHRENHEIT))
    assert out.raw_value == 77.0
    assert out.input_unit is Unit.FAHRENHEIT
    assert out.unit is Unit.CELSIUS
    assert out.normalized_value == pytest.approx(25.0)
    assert out.quality is ReadingQuality.GOOD
    assert out.quality_reason is None


def test_incompatible_unit_rejected() -> None:
    with pytest.raises(UnitNormalizationError):
        process_telemetry_reading(
            _reading(
                sensor_type=SensorType.TEMPERATURE,
                raw_value=400.0,
                input_unit=Unit.PPM,
            )
        )


def test_out_of_range_clamps_but_preserves_raw() -> None:
    out = process_telemetry_reading(
        _reading(
            sensor_type=SensorType.TEMPERATURE,
            raw_value=100.0,
            input_unit=Unit.CELSIUS,
        )
    )
    assert out.raw_value == 100.0
    assert out.normalized_value == 50.0  # SENSOR_VALUE_RANGE high
    assert out.quality is ReadingQuality.SUSPECT
    assert out.quality_reason == "out_of_range_clamped_high"


def test_out_of_range_low() -> None:
    out = process_telemetry_reading(
        _reading(
            sensor_type=SensorType.HUMIDITY,
            raw_value=-5.0,
            input_unit=Unit.PERCENT,
        )
    )
    assert out.raw_value == -5.0
    assert out.normalized_value == 0.0
    assert out.quality is ReadingQuality.SUSPECT
    assert out.quality_reason == "out_of_range_clamped_low"


def test_canonical_passthrough() -> None:
    out = process_telemetry_reading(
        _reading(
            sensor_type=SensorType.CO2,
            raw_value=800.0,
            input_unit=Unit.PPM,
        )
    )
    assert out.normalized_value == 800.0
    assert out.unit is Unit.PPM
    assert out.quality is ReadingQuality.GOOD
