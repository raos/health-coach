"""Replace dexa_scans with body_composition_logs

Revision ID: e1f2a3b4c5d6
Revises: d4e5f6a7b8c9
Create Date: 2026-04-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'e1f2a3b4c5d6'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # body_composition_logs was already created by SQLAlchemy create_all() on startup.
    # Just migrate data from dexa_scans and drop the old table.
    op.execute("""
        INSERT INTO body_composition_logs (user_id, date, body_fat_pct, lean_mass_lbs, fat_mass_lbs, created_at)
        SELECT user_id, scan_date, body_fat_pct, lean_mass_lbs, fat_mass_lbs, created_at
        FROM dexa_scans
    """)

    op.drop_index('ix_dexa_scans_user_id', table_name='dexa_scans')
    op.drop_table('dexa_scans')


def downgrade() -> None:
    op.create_table(
        'dexa_scans',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.UUID(as_uuid=True), nullable=True),
        sa.Column('scan_date', sa.Date(), nullable=False),
        sa.Column('total_weight_lbs', sa.Float(), nullable=False),
        sa.Column('body_fat_pct', sa.Float(), nullable=False),
        sa.Column('fat_mass_lbs', sa.Float(), nullable=False),
        sa.Column('lean_mass_lbs', sa.Float(), nullable=False),
        sa.Column('bone_mass_lbs', sa.Float(), nullable=True),
        sa.Column('visceral_fat_lbs', sa.Float(), nullable=True),
        sa.Column('ag_ratio', sa.Float(), nullable=True),
        sa.Column('almi', sa.Float(), nullable=True),
        sa.Column('ffmi', sa.Float(), nullable=True),
        sa.Column('t_score', sa.Float(), nullable=True),
        sa.Column('facility', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('raw_pdf_path', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_dexa_scans_user_id', 'dexa_scans', ['user_id'])

    op.execute("""
        INSERT INTO dexa_scans (user_id, scan_date, body_fat_pct, lean_mass_lbs, fat_mass_lbs, total_weight_lbs, created_at)
        SELECT user_id, date, body_fat_pct, lean_mass_lbs, fat_mass_lbs,
               COALESCE(lean_mass_lbs, 0) + COALESCE(fat_mass_lbs, 0),
               created_at
        FROM body_composition_logs
    """)

    op.drop_index('ix_body_composition_logs_user_id', table_name='body_composition_logs')
    op.drop_table('body_composition_logs')
