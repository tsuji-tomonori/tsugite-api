# 問い合わせに対応するDBスキーマへ移行する。
"""Persist private inquiries and replies."""

import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"


def upgrade():
    op.create_table(
        "inquiries",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("subject", sa.String(180), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        if_not_exists=True,
    )


def downgrade():
    op.drop_table("inquiries", if_exists=True)
