"""
2단계 Day 4 — enum / 단위 / ORM 메타데이터 단위 테스트.

검증: 센서 단위·범위 커버리지, Day4 테이블 메타데이터 등록,
Site→…→Actuator 관계 속성 존재.
"""

from app.db.base import Base
from app.db.models import Actuator, Farm, Rack, Room, Sensor, Site
from app.domain.enums import ActuatorType, SensorType, Unit
from app.domain.units import SENSOR_DEFAULT_UNIT, default_unit_for, value_range_for


def test_sensor_default_units_cover_all_types() -> None:
    assert set(SENSOR_DEFAULT_UNIT) == set(SensorType)
    assert default_unit_for(SensorType.TEMPERATURE) is Unit.CELSIUS
    assert default_unit_for(SensorType.PPFD) is Unit.MICROMOLE_PER_M2_S


def test_sensor_value_ranges_are_ordered() -> None:
    for sensor_type in SensorType:
        low, high = value_range_for(sensor_type)
        assert low < high


def test_day4_tables_registered_on_metadata() -> None:
    table_names = set(Base.metadata.tables)
    assert {
        "sites",
        "farms",
        "rooms",
        "racks",
        "sensors",
        "actuators",
    } <= table_names


def test_hierarchy_foreign_keys() -> None:
    assert Farm.__table__.c.site_id.foreign_keys
    assert Room.__table__.c.farm_id.foreign_keys
    assert Rack.__table__.c.room_id.foreign_keys
    assert Sensor.__table__.c.room_id.foreign_keys
    assert Actuator.__table__.c.room_id.foreign_keys


def test_site_has_postgis_geography() -> None:
    location = Site.__table__.c.location
    assert location.type.geometry_type.upper() == "POINT"
    assert int(location.type.srid) == 4326


def test_actuator_types_match_product_scope() -> None:
    assert {
        ActuatorType.HVAC,
        ActuatorType.VENTILATION_FAN,
        ActuatorType.DEHUMIDIFIER,
        ActuatorType.IRRIGATION_PUMP,
        ActuatorType.LED,
    } <= set(ActuatorType)
    # crop-zone MVP
    assert ActuatorType.ZONE_VALVE_STRAWBERRY in ActuatorType
    assert ActuatorType.ZONE_VALVE_GRAPE in ActuatorType
    assert ActuatorType.CIRCULATION_FAN in ActuatorType
    assert ActuatorType.HEATER in ActuatorType
    assert ActuatorType.HUMIDIFIER in ActuatorType
