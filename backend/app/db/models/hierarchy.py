"""
공간·농장 계층 모델 (2단계 Day 4).

Site → Farm → Room → Rack
참값/측정/명령 테이블(Day 5~6)이 이 계층을 FK 로 참조한다.
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
    사이트(부지). PostGIS geography Point(4326) 로 위치를 저장한다.

    기상 기준점과의 거리 계산(`ST_DWithin`)에 사용한다.
    """

    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # GeoAlchemy2 Geography — WGS84 경위도. GiST 인덱스는 migration(Day 7)에서 추가.
    location = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text)

    farms: Mapped[list[Farm]] = relationship(back_populates="site")


class Farm(TimestampMixin, Base):
    """농장. 하나의 Site 아래 여러 Farm 이 있을 수 있다."""

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
    """독립 제어 단위인 재배실."""

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
    """재배 랙. 3D 씬의 랙 골격과 대응한다."""

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
