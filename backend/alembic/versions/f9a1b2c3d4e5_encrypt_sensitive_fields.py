"""encrypt_sensitive_fields

Revision ID: f9a1b2c3d4e5
Revises: 4a3252a537f4
Create Date: 2026-04-05 14:00:00.000000

Encrypts sensitive fields at rest using AES-256-GCM:
  - user_profile.mcp_api_key  (+ adds mcp_api_key_lookup for HMAC-based lookups)
  - user_profile.hevy_api_key
  - oauth_tokens.access_token
  - oauth_tokens.refresh_token

Requires FIELD_ENCRYPTION_KEY to be set in the environment before running.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session


# revision identifiers, used by Alembic.
revision: str = 'f9a1b2c3d4e5'
down_revision: Union[str, None] = '4a3252a537f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Add mcp_api_key_lookup column ─────────────────────────────────────
    op.add_column(
        'user_profile',
        sa.Column('mcp_api_key_lookup', sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f('ix_user_profile_mcp_api_key_lookup'),
        'user_profile',
        ['mcp_api_key_lookup'],
        unique=True,
    )

    # ── 2. Encrypt existing plaintext values ─────────────────────────────────
    # Import encryption helpers here so the migration is self-contained and
    # uses the same key the running app uses.
    from database.encryption import encrypt_value, hmac_lookup, _PREFIX

    bind = op.get_bind()
    session = Session(bind=bind)

    # -- user_profile: mcp_api_key (encrypt + set lookup) and hevy_api_key ----
    rows = session.execute(
        sa.text("SELECT id, mcp_api_key, hevy_api_key FROM user_profile")
    ).fetchall()

    for row in rows:
        row_id, mcp_key, hevy_key = row

        new_mcp = mcp_key
        new_mcp_lookup = None
        if mcp_key and not mcp_key.startswith(_PREFIX):
            new_mcp = encrypt_value(mcp_key)
            new_mcp_lookup = hmac_lookup(mcp_key)
        elif mcp_key and mcp_key.startswith(_PREFIX):
            # Already encrypted (shouldn't happen on first run, but be safe)
            from database.encryption import decrypt_value
            new_mcp_lookup = hmac_lookup(decrypt_value(mcp_key))

        new_hevy = hevy_key
        if hevy_key and not hevy_key.startswith(_PREFIX):
            new_hevy = encrypt_value(hevy_key)

        session.execute(
            sa.text(
                "UPDATE user_profile "
                "SET mcp_api_key = :mcp, mcp_api_key_lookup = :lookup, hevy_api_key = :hevy "
                "WHERE id = :id"
            ),
            {"mcp": new_mcp, "lookup": new_mcp_lookup, "hevy": new_hevy, "id": row_id},
        )

    # -- oauth_tokens: access_token and refresh_token -------------------------
    token_rows = session.execute(
        sa.text("SELECT id, access_token, refresh_token FROM oauth_tokens")
    ).fetchall()

    for row in token_rows:
        row_id, access, refresh = row

        new_access = access
        if access and not access.startswith(_PREFIX):
            new_access = encrypt_value(access)

        new_refresh = refresh
        if refresh and not refresh.startswith(_PREFIX):
            new_refresh = encrypt_value(refresh)

        session.execute(
            sa.text(
                "UPDATE oauth_tokens "
                "SET access_token = :access, refresh_token = :refresh "
                "WHERE id = :id"
            ),
            {"access": new_access, "refresh": new_refresh, "id": row_id},
        )

    session.commit()


def downgrade() -> None:
    # Decrypt values back to plaintext.
    from database.encryption import decrypt_value

    bind = op.get_bind()
    session = Session(bind=bind)

    # -- user_profile ---------------------------------------------------------
    rows = session.execute(
        sa.text("SELECT id, mcp_api_key, hevy_api_key FROM user_profile")
    ).fetchall()
    for row in rows:
        row_id, mcp_key, hevy_key = row
        session.execute(
            sa.text(
                "UPDATE user_profile "
                "SET mcp_api_key = :mcp, hevy_api_key = :hevy "
                "WHERE id = :id"
            ),
            {
                "mcp": decrypt_value(mcp_key) if mcp_key else mcp_key,
                "hevy": decrypt_value(hevy_key) if hevy_key else hevy_key,
                "id": row_id,
            },
        )

    # -- oauth_tokens ---------------------------------------------------------
    token_rows = session.execute(
        sa.text("SELECT id, access_token, refresh_token FROM oauth_tokens")
    ).fetchall()
    for row in token_rows:
        row_id, access, refresh = row
        session.execute(
            sa.text(
                "UPDATE oauth_tokens "
                "SET access_token = :access, refresh_token = :refresh "
                "WHERE id = :id"
            ),
            {
                "access": decrypt_value(access) if access else access,
                "refresh": decrypt_value(refresh) if refresh else refresh,
                "id": row_id,
            },
        )

    session.commit()

    # Drop the lookup column and its index.
    op.drop_index(op.f('ix_user_profile_mcp_api_key_lookup'), table_name='user_profile')
    op.drop_column('user_profile', 'mcp_api_key_lookup')
