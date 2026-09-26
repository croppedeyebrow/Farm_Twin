"""
MVP seed data (2단계 Day 7).

목적
----
신규 환경에서 migration 직후 바로 관제·시뮬을 돌릴 수 있는
최소 농장 그래프를 넣는다.

구성
----
- Site 1 (서울 시청 근처 Point) → Farm 1 → Room 1
- Rack 3 (1단계 3D 씬 R1~R3 과 좌표 대응)
- Sensor 5종 / Actuator 5종
- FarmState 초기 참값 (version=1)
- ControlRule 1 (고온 시 HVAC)
- SimulationRun 1 (seed=42, CREATED)

고정 UUID
---------
문서·테스트·프론트가 같은 ID 를 쓰도록 하드코딩한다.
(데이터_사전.md 참고)

사용
----
    uv run python -m app.db.seed
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, select

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


def _stable_uuid(prefix: str, index: int) -> uuid.UUID:
    """prefix(8 hex) + index 기반 고정 UUID. 종류가 9개를 넘어도 안전."""
    return uuid.UUID(f"{prefix}-5555-5555-5555-{index:012d}")


async def _ensure_room_devices(session, room_id: uuid.UUID) -> int:
    """
    기존 seed 농장에 빠진 센서/액추에이터 타입을 추가한다.

    목적: crop-zone·heater 등 enum 확장 후에도 force reseeding 없이 보완.
    """
    added = 0
    existing_sensors = {
        row.sensor_type
        for row in (
            await session.scalars(select(Sensor).where(Sensor.room_id == room_id))
        ).all()
    }
    for index, sensor_type in enumerate(SensorType, start=1):
        if sensor_type in existing_sensors:
            continue
        session.add(
            Sensor(
                id=_stable_uuid("66666666", index),
                room_id=room_id,
                rack_id=None,
                code=sensor_type.value,
                name=sensor_type.value.replace("_", " ").title(),
                sensor_type=sensor_type,
                unit=default_unit_for(sensor_type),
                model_version="v1",
            )
        )
        added += 1

    existing_actuators = {
        row.actuator_type
        for row in (
            await session.scalars(select(Actuator).where(Actuator.room_id == room_id))
        ).all()
    }
    for index, actuator_type in enumerate(ActuatorType, start=1):
        if actuator_type in existing_actuators:
            continue
        session.add(
            Actuator(
                id=_stable_uuid("77777777", index),
                room_id=room_id,
                code=actuator_type.value,
                name=actuator_type.value.replace("_", " ").title(),
                actuator_type=actuator_type,
                mode=ActuatorMode.OFF,
                output_ratio=0.0,
            )
        )
        added += 1
    return added


async def seed_mvp(*, force: bool = False) -> dict[str, str]:
    """
    MVP 데이터를 삽입한다.

    - 기본: 동일 FARM_ID 가 있으면 skip (멱등) + 빠진 장치만 보완
    - force=True: Site 를 SQL DELETE 한 뒤 다시 심는다
      (ORM delete(Farm) 은 rooms.farm_id NULL 시도 → NOT NULL 위반.
       DB ON DELETE CASCADE 를 쓰려면 delete(Site) 가 안전하다.)
      commit 후 expunge_all 로 identity map 충돌 경고를 막는다.
    """
    async with SessionLocal() as session:
        if not force:
            existing = await session.scalar(select(Farm).where(Farm.id == FARM_ID))
            if existing:
                patched = await _ensure_room_devices(session, ROOM_ID)
                if patched:
                    await session.commit()
                return {
                    "status": "skipped",
                    "farm_id": str(FARM_ID),
                    "devices_patched": str(patched),
                }
        else:
            # ORM session.delete(Farm) 은 relationship 때문에 rooms.farm_id 를
            # NULL 로 만들려다 NOT NULL 위반이 난다.
            # Site 부터 SQL DELETE → DB ON DELETE CASCADE 로 하위 전부 제거.
            await session.execute(delete(Site).where(Site.id == SITE_ID))
            await session.commit()
            session.expunge_all()

        # WKT POINT(lon lat) — GeoAlchemy2 Geography(4326)
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

        # 3D GrowingRoomScene 의 RACK_POSITIONS 와 x 간격을 맞춘다.
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

        # 배지수분만 랙 부착, 나머지는 룸 공용 센서로 둔다.
        sensors: list[Sensor] = []
        for index, sensor_type in enumerate(SensorType, start=1):
            sensors.append(
                Sensor(
                    id=_stable_uuid("66666666", index),
                    room_id=ROOM_ID,
                    rack_id=(
                        racks[0].id
                        if sensor_type is SensorType.SUBSTRATE_MOISTURE
                        else None
                    ),
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
                id=_stable_uuid("77777777", i),
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

        # 참값 초기 상태 — 센서 noise 가 아직 없는 환경 모델 값
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
        # 4단계 규칙 엔진이 사용할 샘플 규칙 (히스테리시스)
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
