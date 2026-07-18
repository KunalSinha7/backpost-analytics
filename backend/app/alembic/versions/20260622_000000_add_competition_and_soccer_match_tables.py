"""Add competition and soccer match tables

Revision ID: 970a30281eff
Revises: fe56fa70289e
Create Date: 2026-06-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "970a30281eff"
down_revision: str | None = "fe56fa70289e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "competition",
        sa.Column("statsbomb_id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("country_name", sqlmodel.AutoString(length=100), nullable=False),
        sa.Column("competition_name", sqlmodel.AutoString(length=255), nullable=False),
        sa.Column("competition_gender", sqlmodel.AutoString(length=20), nullable=False),
        sa.Column("competition_youth", sa.Boolean(), nullable=False),
        sa.Column("competition_international", sa.Boolean(), nullable=False),
        sa.Column("season_name", sqlmodel.AutoString(length=100), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("statsbomb_id", "season_id"),
    )
    op.create_index(op.f("ix_competition_season_id"), "competition", ["season_id"], unique=False)
    op.create_index(op.f("ix_competition_statsbomb_id"), "competition", ["statsbomb_id"], unique=False)

    op.create_table(
        "soccer_match",
        sa.Column("statsbomb_id", sa.Integer(), nullable=False),
        sa.Column("competition_id", sa.Uuid(), nullable=False),
        sa.Column("match_date", sqlmodel.AutoString(length=20), nullable=False),
        sa.Column("kick_off", sqlmodel.AutoString(length=20), nullable=True),
        sa.Column("home_team", sqlmodel.AutoString(length=255), nullable=False),
        sa.Column("away_team", sqlmodel.AutoString(length=255), nullable=False),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("stadium", sqlmodel.AutoString(length=255), nullable=True),
        sa.Column("referee", sqlmodel.AutoString(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["competition_id"], ["competition.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_soccer_match_statsbomb_id"), "soccer_match", ["statsbomb_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_soccer_match_statsbomb_id"), table_name="soccer_match")
    op.drop_table("soccer_match")
    op.drop_index(op.f("ix_competition_statsbomb_id"), table_name="competition")
    op.drop_index(op.f("ix_competition_season_id"), table_name="competition")
    op.drop_table("competition")
