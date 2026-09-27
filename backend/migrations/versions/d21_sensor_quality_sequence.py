"""
Day 21 — 센서 스트림 sequence·누락 마커.

Revision ID: d21_sensor_quality_seq
Revises: d20_telemetry_raw_norm
Create Date: 2026-09-27

변경
----
- source_sequence: 센서 스트림별 송신 번호 (중복·누락 판정 기준)
- value / raw_value nullable: quality=missing 마커 행은 측정값이 없다
- CHECK: missing 이 아니면 value·raw_value 필수
- UNIQUE (simulation_run_id, sensor_id, source_sequence) WHERE NOT NULL
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d21_sensor_quality_seq"
down_revision: str | Sequence[str] | None = "d20_telemetry_raw_norm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sensor_readings",
        sa.Column("source_sequence", sa.Integer(), nullable=True),
    )
    op.alter_column("sensor_readings", "value", nullable=True)
    op.alter_column("sensor_readings", "raw_value", nullable=True)
    op.create_check_constraint(
        "ck_sensor_readings_source_sequence_nonneg",
        "sensor_readings",
        "source_sequence IS NULL OR source_sequence >= 0",
    )
    op.create_check_constraint(
        "ck_sensor_readings_value_present",
        "sensor_readings",
        "quality = 'missing' OR (value IS NOT NULL AND raw_value IS NOT NULL)",
    )
    op.create_index(
        "uq_sensor_readings_run_sensor_source_seq",
        "sensor_readings",
        ["simulation_run_id", "sensor_id", "source_sequence"],
        unique=True,
        postgresql_where=sa.text("source_sequence IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_sensor_readings_run_sensor_source_seq",
        table_name="sensor_readings",
    )
    op.drop_constraint(
        "ck_sensor_readings_value_present",
        "sensor_readings",
        type_="check",
    )
    op.drop_constraint(
        "ck_sensor_readings_source_sequence_nonneg",
        "sensor_readings",
        type_="check",
    )
    # 값이 없는 누락 마커는 NOT NULL 로 되돌릴 수 없어 삭제한다
    op.execute(sa.text("DELETE FROM sensor_readings WHERE value IS NULL"))
    op.alter_column("sensor_readings", "raw_value", nullable=False)
    op.alter_column("sensor_readings", "value", nullable=False)
    op.drop_column("sensor_readings", "source_sequence")
