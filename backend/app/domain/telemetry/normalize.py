"""
단위 정규화·범위 clamp (6단계 Day 20).

규칙
----
1. input_unit → 센서 타입 기본 단위로 변환 (가능하면)
2. 호환되지 않는 단위는 UnitNormalizationError (적재 거부)
3. 물리 범위 밖이면 clamp 하고 quality=SUSPECT + reason
4. raw_value 는 절대 수정하지 않는다
"""

from __future__ import annotations

from collections.abc import Callable

from app.domain.enums import ReadingQuality, SensorType, Unit
from app.domain.units import default_unit_for, value_range_for

_CONVERTERS: dict[tuple[Unit, Unit], Callable[[float], float]] = {
    (Unit.CELSIUS, Unit.CELSIUS): lambda v: v,
    (Unit.FAHRENHEIT, Unit.CELSIUS): lambda v: (v - 32.0) * 5.0 / 9.0,
    (Unit.PERCENT, Unit.PERCENT): lambda v: v,
    (Unit.PPM, Unit.PPM): lambda v: v,
    (Unit.MICROMOLE_PER_M2_S, Unit.MICROMOLE_PER_M2_S): lambda v: v,
}


class UnitNormalizationError(ValueError):
    """지원하지 않는 단위 변환."""


def normalize_unit_value(
    *,
    sensor_type: SensorType,
    raw_value: float,
    input_unit: Unit,
) -> tuple[float, Unit]:
    """
    raw_value 를 센서 타입의 정규화 단위로 바꾼다.

    Returns
    -------
    (normalized_value, canonical_unit)
    """
    target = default_unit_for(sensor_type)
    converter = _CONVERTERS.get((input_unit, target))
    if converter is None:
        raise UnitNormalizationError(
            f"cannot normalize {input_unit.value} → {target.value} "
            f"for sensor_type={sensor_type.value}"
        )
    return converter(raw_value), target


def apply_range_quality(
    *,
    sensor_type: SensorType,
    normalized_value: float,
) -> tuple[float, ReadingQuality, str | None]:
    """
    정규화 값을 물리 범위에 clamp 하고 quality 를 붙인다.

    Returns
    -------
    (stored_value, quality, quality_reason)
    """
    low, high = value_range_for(sensor_type)
    if normalized_value < low:
        return low, ReadingQuality.SUSPECT, "out_of_range_clamped_low"
    if normalized_value > high:
        return high, ReadingQuality.SUSPECT, "out_of_range_clamped_high"
    return normalized_value, ReadingQuality.GOOD, None
