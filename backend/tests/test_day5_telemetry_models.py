"""2단계 Day 5 — 참값/측정값/시뮬레이션·시간 컬럼 의미 테스트."""

from app.db.base import Base
from app.db.models import FarmState, SensorReading, SimulationRun, WeatherSnapshot
from app.domain.time_semantics import TIME_COLUMN_SEMANTICS, describe_time_column


def test_day5_tables_registered() -> None:
    names = set(Base.metadata.tables)
    assert {
        "simulation_runs",
        "weather_snapshots",
        "farm_states",
        "sensor_readings",
    } <= names


def test_farm_state_one_row_per_room_unique() -> None:
    constraints = {c.name for c in FarmState.__table__.constraints if c.name}
    assert "uq_farm_states_room" in constraints
    assert "ck_farm_states_version_positive" in constraints


def test_sensor_reading_run_sequence_unique() -> None:
    constraints = {c.name for c in SensorReading.__table__.constraints if c.name}
    assert "uq_sensor_readings_run_sequence" in constraints


def test_sensor_reading_time_columns_exist() -> None:
    columns = set(SensorReading.__table__.c.keys())
    assert {"simulation_time", "sampled_at", "ingested_at"} <= columns


def test_weather_snapshot_time_columns_exist() -> None:
    columns = set(WeatherSnapshot.__table__.c.keys())
    assert {"simulation_time", "sampled_at", "ingested_at", "sequence"} <= columns


def test_simulation_run_clock_fields() -> None:
    columns = set(SimulationRun.__table__.c.keys())
    assert {
        "simulation_time_seconds",
        "time_scale",
        "random_seed",
        "weather_mode",
        "started_at",
        "ended_at",
        "worker_heartbeat_at",
    } <= columns


def test_sensor_reading_query_indexes() -> None:
    index_names = {idx.name for idx in SensorReading.__table__.indexes}
    assert "ix_sensor_readings_sensor_id_simulation_time" in index_names
    assert "ix_sensor_readings_farm_id_simulation_time" in index_names


def test_time_semantics_cover_core_columns() -> None:
    required = {
        "simulation_time",
        "sampled_at",
        "ingested_at",
        "created_at",
        "updated_at",
        "started_at",
        "ended_at",
        "worker_heartbeat_at",
    }
    assert required <= set(TIME_COLUMN_SEMANTICS)
    assert "가상 시계" in describe_time_column("simulation_time")
    assert "적재" in describe_time_column("ingested_at")
