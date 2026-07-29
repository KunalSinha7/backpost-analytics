"""add_player_table

Revision ID: b28544af579f
Revises: 139e7533a88f
Create Date: 2026-07-28 23:20:32.906094

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'b28544af579f'
down_revision = '139e7533a88f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('player',
    sa.Column('statsbomb_id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('nickname', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('nationality', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_player_name'), 'player', ['name'], unique=False)
    op.create_index(op.f('ix_player_statsbomb_id'), 'player', ['statsbomb_id'], unique=True)


def downgrade():
    op.drop_index(op.f('ix_player_statsbomb_id'), table_name='player')
    op.drop_index(op.f('ix_player_name'), table_name='player')
    op.drop_table('player')
