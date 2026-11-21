"""Create the API inventory, project grants and append-only event stream."""

import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None


def upgrade():
    op.create_table(
        "assets",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("spec", sa.Text(), nullable=False),
        sa.Column("targets", sa.Text(), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        if_not_exists=True,
    )
    op.create_table(
        "access_rights",
        sa.Column("id", sa.String(140), primary_key=True),
        sa.Column("asset_id", sa.String(32), nullable=False),
        sa.Column("project", sa.String(64), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        if_not_exists=True,
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(180), nullable=False),
        sa.Column("project", sa.String(64), nullable=False),
        sa.Column("owner", sa.String(64), nullable=False),
        sa.Column("asset_id", sa.String(32), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("request_id", sa.String(40), nullable=False),
        if_not_exists=True,
    )


def downgrade():
    for name in ("audit_events", "access_rights", "assets"):
        op.drop_table(name, if_exists=True)
