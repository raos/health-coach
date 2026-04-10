"""add body_fat_pct to weight_logs and weight_goal_lbs to user_profile

Revision ID: 78c65aa8264d
Revises: f9a1b2c3d4e5
Create Date: 2026-04-10 02:03:24.654952

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78c65aa8264d'
down_revision: Union[str, None] = 'f9a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user_profile', sa.Column('weight_goal_lbs', sa.Float(), nullable=True))
    op.add_column('weight_logs', sa.Column('body_fat_pct', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('weight_logs', 'body_fat_pct')
    op.drop_column('user_profile', 'weight_goal_lbs')
