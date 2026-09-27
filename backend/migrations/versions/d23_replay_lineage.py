"""
Day 23 — replay 입력·lineage.

Revision ID: d23_replay_lineage
Revises: d21_sensor_quality_seq
Create Date: 2026-09-27

변경
----
simulation_runs
- rule_set_version : 스텝 시점 활성 규칙 묶음 지문 (rules.v1:<hash>)
- initial_state    : 첫 스텝 직전 체크포인트 (참값·설비·스트림·게이트)
- replay_of_run_id : 재생 run 의 원본 run
- replay_input     : 재생 run 의 입력 (외기·수동 제어 일정·기대 결과)

control_commands
- rule_version       : 명령 시점 규칙 개정 번호 (규칙 행이 갱신돼도 남는다)
- trigger_reading_id : 판정 근거가 된 측정 행
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d23_replay_lineage"
down_revision: str | Sequence[str] | None = "d21_sensor_quality_seq"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("simulation_runs", sa.Column("rule_set_version", sa.String(64)))
    op.add_column(
        "simulation_runs",
        sa.Column("initial_state", postgresql.JSONB(astext_type=sa.Text())),
    )
    op.add_column(
        "simulation_runs",
        sa.Column("replay_of_run_id", postgresql.UUID(as_uuid=True)),
    )
    op.add_column(
        "simulation_runs",
        sa.Column("replay_input", postgresql.JSONB(astext_type=sa.Text())),
    )
    op.create_foreign_key(
        "fk_simulation_runs_replay_of_run_id",
        "simulation_runs",
        "simulation_runs",
        ["replay_of_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_simulation_runs_replay_of_run_id",
        "simulation_runs",
        ["replay_of_run_id"],
    )

    op.add_column("control_commands", sa.Column("rule_version", sa.Integer()))
    op.add_column(
        "control_commands",
        sa.Column("trigger_reading_id", postgresql.UUID(as_uuid=True)),
    )
    op.create_foreign_key(
        "fk_control_commands_trigger_reading_id",
        "control_commands",
        "sensor_readings",
        ["trigger_reading_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_control_commands_trigger_reading_id",
        "control_commands",
        ["trigger_reading_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_control_commands_trigger_reading_id", table_name="control_commands")
    op.drop_constraint(
        "fk_control_commands_trigger_reading_id",
        "control_commands",
        type_="foreignkey",
    )
    op.drop_column("control_commands", "trigger_reading_id")
    op.drop_column("control_commands", "rule_version")

    op.drop_index("ix_simulation_runs_replay_of_run_id", table_name="simulation_runs")
    op.drop_constraint(
        "fk_simulation_runs_replay_of_run_id",
        "simulation_runs",
        type_="foreignkey",
    )
    op.drop_column("simulation_runs", "replay_input")
    op.drop_column("simulation_runs", "replay_of_run_id")
    op.drop_column("simulation_runs", "initial_state")
    op.drop_column("simulation_runs", "rule_set_version")
