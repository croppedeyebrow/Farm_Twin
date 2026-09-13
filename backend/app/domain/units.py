"""
센서 타입 ↔ 기본 단위 매핑 (2단계 Day 4).

정규화 파이프라인(6단계)과 seed/API 가 같은 기준을 쓰도록
도메인 계층에 고정한다.
"""

from app.domain.enums import SensorType, Unit

# 센서 타입별 정규화 단위.
SENSOR_DEFAULT_UNIT: dict[SensorType, Unit] = {
    SensorType.TEMPERATURE: Unit.CELSIUS,
    SensorType.HUMIDITY: Unit.PERCENT,
    SensorType.CO2: Unit.PPM,
    SensorType.SUBSTRATE_MOISTURE: Unit.PERCENT,
    SensorType.PPFD: Unit.MICROMOLE_PER_M2_S,
}

# MVP 물리 범위 (clamp / quality 판정 기초). inclusive.
SENSOR_VALUE_RANGE: dict[SensorType, tuple[float, float]] = {
    SensorType.TEMPERATURE: (-10.0, 50.0),
    SensorType.HUMIDITY: (0.0, 100.0),
    SensorType.CO2: (300.0, 5000.0),
    SensorType.SUBSTRATE_MOISTURE: (0.0, 100.0),
    SensorType.PPFD: (0.0, 2000.0),
}


def default_unit_for(sensor_type: SensorType) -> Unit:
    """센서 타입의 기본 저장 단위를 반환한다."""
    return SENSOR_DEFAULT_UNIT[sensor_type]


def value_range_for(sensor_type: SensorType) -> tuple[float, float]:
    """센서 타입의 (min, max) 허용 범위를 반환한다."""
    return SENSOR_VALUE_RANGE[sensor_type]
