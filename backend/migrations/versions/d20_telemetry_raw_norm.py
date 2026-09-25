"""
Day 20 — sensor_readings raw/normalized/quality 분리.

Revision ID: d20_telemetry_raw_norm
Revises: c18bc480b9e7
Create Date: 2026-09-24

추가 컬럼
---------
- raw_value: clamp·단위변환 전 원본
- input_unit: ingest 시점 단위
- quality_reason: clamp 등 사유 (Day 21+ 확장)
- telemetry_schema_version: reading 계약 버전

기존 행이 있으면 value/unit 으로 backfill 한다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d20_telemetry_raw_norm"
down_revision: str | Sequence[str] | None = "c18bc480b9e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sensor_readings",
        sa.Column("raw_value", sa.Float(), nullable=True),
    )
    op.add_column(
        "sensor_readings",
        sa.Column("input_unit", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "sensor_readings",
        sa.Column("quality_reason", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "sensor_readings",
        sa.Column(
            "telemetry_schema_version",
            sa.String(length=64),
            nullable=False,
            server_default="telemetry.reading.v1",
        ),
    )

    # 기존 행: raw = value, input_unit = unit (이미 정규화돼 저장됐던 가정)
    op.execute(
        sa.text(
            "UPDATE sensor_readings "
            "SET raw_value = value, input_unit = unit "
            "WHERE raw_value IS NULL"
        )
    )

    op.alter_column("sensor_readings", "raw_value", nullable=False)
    op.alter_column("sensor_readings", "input_unit", nullable=False)
    op.alter_column(
        "sensor_readings",
        "telemetry_schema_version",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("sensor_readings", "telemetry_schema_version")
    op.drop_column("sensor_readings", "quality_reason")
    op.drop_column("sensor_readings", "input_unit")
    op.drop_column("sensor_readings", "raw_value")
