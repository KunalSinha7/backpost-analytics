"""add_started_to_lineup

Revision ID: 139e7533a88f
Revises: 551ae34afebc
Create Date: 2026-07-02 02:27:06.991222

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '139e7533a88f'
down_revision = '551ae34afebc'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('lineup', sa.Column('started', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade():
    op.drop_column('lineup', 'started')
