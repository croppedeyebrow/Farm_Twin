"""
센서 타입 ↔ 기본 단위·물리 범위 (2단계 Day 4 + crop-zone MVP).

목적
----
정규화 파이프라인·seed·API·시뮬 clamp 가 같은 min/max·단위를 쓰게 한다.

이유
----
타입마다 다른 범위를 쓰면 재현성·품질 판정·구역 파생값이 깨진다.
구역 MVP 센서(EC·근권온도·pH·엽면습윤·유량)도 여기서 한곳에 고정한다.
"""

from app.domain.enums import SensorType, Unit

SENSOR_DEFAULT_UNIT: dict[SensorType, Unit] = {
    SensorType.TEMPERATURE: Unit.CELSIUS,
    SensorType.HUMIDITY: Unit.PERCENT,
    SensorType.CO2: Unit.PPM,
    SensorType.SUBSTRATE_MOISTURE: Unit.PERCENT,
    SensorType.PPFD: Unit.MICROMOLE_PER_M2_S,
    SensorType.SUBSTRATE_EC: Unit.MS_PER_CM,
    SensorType.SUBSTRATE_TEMPERATURE: Unit.CELSIUS,
    SensorType.NUTRIENT_PH: Unit.PH,
    SensorType.LEAF_WETNESS: Unit.MINUTES,
    SensorType.IRRIGATION_FLOW: Unit.LITER_PER_MIN,
}

# inclusive MVP 물리 범위 (clamp / quality)
SENSOR_VALUE_RANGE: dict[SensorType, tuple[float, float]] = {
    SensorType.TEMPERATURE: (-10.0, 50.0),
    SensorType.HUMIDITY: (0.0, 100.0),
    SensorType.CO2: (300.0, 5000.0),
    SensorType.SUBSTRATE_MOISTURE: (0.0, 100.0),
    SensorType.PPFD: (0.0, 2000.0),
    SensorType.SUBSTRATE_EC: (0.0, 10.0),
    SensorType.SUBSTRATE_TEMPERATURE: (-5.0, 45.0),
    SensorType.NUTRIENT_PH: (4.0, 9.0),
    SensorType.LEAF_WETNESS: (0.0, 1440.0),
    SensorType.IRRIGATION_FLOW: (0.0, 100.0),
}


def default_unit_for(sensor_type: SensorType) -> Unit:
    """센서 타입의 기본 저장 단위."""
    return SENSOR_DEFAULT_UNIT[sensor_type]


def value_range_for(sensor_type: SensorType) -> tuple[float, float]:
    """센서 타입의 (min, max) 허용 범위."""
    return SENSOR_VALUE_RANGE[sensor_type]
