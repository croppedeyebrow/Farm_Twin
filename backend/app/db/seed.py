"""
MVP seed data (2단계 Day 7).

1개 Site / Farm / Room, 랙 3개, 센서·액추에이터, 초기 FarmState,
온도 제어 규칙 1개, SimulationRun 1개를 넣는다.

사용:
    uv run python -m app.db.seed
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from app.db.models import (
    Actuator,
    ControlRule,
    Farm,
    FarmState,
    Rack,
    Room,
    Sensor,
    SimulationRun,
    Site,
)
from app.db.session import SessionLocal, engine
from app.domain.enums import (
    ActuatorMode,
    ActuatorType,
    RuleComparator,
    SensorType,
    SimulationStatus,
    WeatherMode,
)
from app.domain.units import default_unit_for

# 고정 UUID — 문서·테스트·프론트에서 재현 가능하게
SITE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
FARM_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
ROOM_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
RUN_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")


async def seed_mvp(*, force: bool = False) -> dict[str, str]:
    """MVP 데이터를 삽입한다. 이미 Farm 이 있으면 건너뛴다(force 제외)."""
    async with SessionLocal() as session:
        existing = await session.scalar(select(Farm).where(Farm.id == FARM_ID))
        if existing and not force:
            return {"status": "skipped", "farm_id": str(FARM_ID)}

        if existing and force:
            await session.delete(existing)
            await session.commit()

        site = Site(
            id=SITE_ID,
            name="Seoul Demo Site",
            location=WKTElement("POINT(126.9780 37.5665)", srid=4326),
            description="MVP seed site (Seoul City Hall approx.)",
        )
        farm = Farm(
            id=FARM_ID,
            site_id=SITE_ID,
            code="DEMO-01",
            name="FarmTwin Demo Farm",
            description="1단계 3D 재배실과 대응하는 MVP 농장",
        )
        room = Room(
            id=ROOM_ID,
            farm_id=FARM_ID,
            code="ROOM-A",
            name="재배실 A",
            description="독립 제어 재배실",
        )
        session.add_all([site, farm, room])

        racks = [
            Rack(
                id=uuid.UUID(f"55555555-5555-5555-5555-55555555555{i}"),
                room_id=ROOM_ID,
                code=f"R{i}",
                name=f"Rack {i}",
                position_x=-2.2 + (i - 1) * 2.2,
                position_y=0.0,
                position_z=-0.4,
            )
            for i in (1, 2, 3)
        ]
        session.add_all(racks)

        sensors: list[Sensor] = []
        for index, sensor_type in enumerate(SensorType, start=1):
            sensors.append(
                Sensor(
                    id=uuid.UUID(f"66666666-6666-6666-6666-66666666666{index}"),
                    room_id=ROOM_ID,
                    rack_id=racks[0].id if sensor_type is SensorType.SUBSTRATE_MOISTURE else None,
                    code=sensor_type.value,
                    name=sensor_type.value.replace("_", " ").title(),
                    sensor_type=sensor_type,
                    unit=default_unit_for(sensor_type),
                    model_version="v1",
                )
            )
        session.add_all(sensors)

        actuators = [
            Actuator(
                id=uuid.UUID(f"77777777-7777-7777-7777-77777777777{i}"),
                room_id=ROOM_ID,
                code=actuator_type.value,
                name=actuator_type.value.replace("_", " ").title(),
                actuator_type=actuator_type,
                mode=ActuatorMode.OFF,
                output_ratio=0.0,
            )
            for i, actuator_type in enumerate(ActuatorType, start=1)
        ]
        session.add_all(actuators)

        session.add(
            FarmState(
                farm_id=FARM_ID,
                room_id=ROOM_ID,
                simulation_run_id=None,
                version=1,
                temperature_c=24.0,
                humidity_pct=60.0,
                co2_ppm=800.0,
                substrate_moisture_pct=45.0,
                ppfd_umol=0.0,
                simulation_time=0.0,
            )
        )
        session.add(
            ControlRule(
                farm_id=FARM_ID,
                room_id=ROOM_ID,
                name="cool_on_high_temp",
                version=1,
                enabled=True,
                priority=10,
                metric=SensorType.TEMPERATURE,
                comparator=RuleComparator.GT,
                start_threshold=28.0,
                stop_threshold=25.0,
                target_actuator_type=ActuatorType.HVAC,
                target_mode=ActuatorMode.ON,
                target_output_ratio=0.8,
                cooldown_seconds=30.0,
                min_on_seconds=60.0,
                description="온도 상승 시 냉방, 하강 시 정지 (히스테리시스)",
            )
        )
        session.add(
            SimulationRun(
                id=RUN_ID,
                farm_id=FARM_ID,
                room_id=ROOM_ID,
                name="MVP baseline run",
                status=SimulationStatus.CREATED,
                random_seed=42,
                weather_mode=WeatherMode.SYNTHETIC,
                environment_model_version="v1",
                simulation_time_seconds=0.0,
                time_scale=1.0,
                started_at=None,
                notes=f"seeded_at={datetime.now(UTC).isoformat()}",
            )
        )

        await session.commit()
        return {
            "status": "seeded",
            "site_id": str(SITE_ID),
            "farm_id": str(FARM_ID),
            "room_id": str(ROOM_ID),
            "simulation_run_id": str(RUN_ID),
        }


async def _main() -> None:
    result = await seed_mvp()
    print(result)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
