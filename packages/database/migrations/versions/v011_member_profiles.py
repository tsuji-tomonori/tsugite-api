# 利用者プロフィールに対応するDBスキーマへ移行する。
"""Store the portal member's names and directory email by subject."""

import sqlalchemy as sa
from alembic import op

revision = "011"
down_revision = "010"


def upgrade() -> None:
    op.create_table(
        "portal_member_profiles",
        sa.Column("subject", sa.String(180), primary_key=True),
        sa.Column("full_name", sa.String(120)),
        sa.Column("display_name", sa.String(80)),
        sa.Column("email", sa.String(320)),
        sa.Column("email_synced_at", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer(), nullable=False),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("portal_member_profiles", if_exists=True)
