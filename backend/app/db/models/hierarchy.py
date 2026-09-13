"""
공간·농장 계층 모델 (2단계 Day 4).

계층
----
Site → Farm → Room → Rack

의미
----
- Site: 지리 위치(PostGIS). 기상 기준점·거리 계산.
- Farm: 운영 단위. API `/farms/{id}` 의 루트.
- Room: 독립 제어 단위. FarmState / 규칙 / 센서·액추에이터 소속.
- Rack: 재배 랙. 1단계 R3F 씬의 랙과 code·좌표로 대응.

하위 시계열·명령 테이블(Day 5~6)은 이 계층을 FK 로 참조한다.
code 는 부모 스코프 안에서 UNIQUE (사람이 읽는 식별자).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from geoalchemy2 import Geography
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.db.models.equipment import Actuator, Sensor


class Site(TimestampMixin, Base):
    """
    사이트(부지).

    location: WGS84 Point geography.
    ST_DWithin 등으로 기상 관측점과의 거리를 계산할 때 사용한다.
    GiST 인덱스는 GeoAlchemy2 가 컬럼 생성 시 자동으로 만든다 (Day 7 migration).
    """

    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # GeoAlchemy2 Geography — WGS84 경위도 (lon, lat)
    location = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text)

    farms: Mapped[list[Farm]] = relationship(back_populates="site")


class Farm(TimestampMixin, Base):
    """
    농장.

    하나의 Site 아래 여러 Farm 이 있을 수 있다.
    seed 고정 ID: 22222222-... (데이터_사전.md)
    """

    __tablename__ = "farms"
    __table_args__ = (
        UniqueConstraint("site_id", "code", name="uq_farms_site_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    site: Mapped[Site] = relationship(back_populates="farms")
    rooms: Mapped[list[Room]] = relationship(back_populates="farm")


class Room(TimestampMixin, Base):
    """
    독립 제어 단위인 재배실.

    센서·액추에이터·FarmState·ControlRule 이 여기에 달린다.
    """

    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_rooms_farm_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    farm: Mapped[Farm] = relationship(back_populates="rooms")
    racks: Mapped[list[Rack]] = relationship(back_populates="room")
    sensors: Mapped[list[Sensor]] = relationship(back_populates="room")
    actuators: Mapped[list[Actuator]] = relationship(back_populates="room")


class Rack(TimestampMixin, Base):
    """
    재배 랙.

    position_* 는 룸 로컬 좌표(선택). 1단계 GrowingRoomScene 랙과 맞춤.
    """

    __tablename__ = "racks"
    __table_args__ = (
        UniqueConstraint("room_id", "code", name="uq_racks_room_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # 3D/레이아웃용 선택 좌표 (룸 로컬). 없으면 null.
    position_x: Mapped[float | None] = mapped_column()
    position_y: Mapped[float | None] = mapped_column()
    position_z: Mapped[float | None] = mapped_column()

    room: Mapped[Room] = relationship(back_populates="racks")
    sensors: Mapped[list[Sensor]] = relationship(back_populates="rack")
