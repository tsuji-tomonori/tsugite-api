"""Portal governance and scoped invocation history."""

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"


def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("assets")}
    if "removed_at" not in columns:
        op.add_column("assets", sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "portal_members",
        sa.Column("subject", sa.String(length=180), primary_key=True, nullable=False),
        sa.Column("username", sa.String(length=180), primary_key=False, nullable=False),
        sa.Column("project", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("role", sa.String(length=16), primary_key=False, nullable=False),
        sa.Column("deleted", sa.Boolean(), primary_key=False, nullable=False),
        if_not_exists=True,
    )
    op.create_table(
        "notices",
        sa.Column("id", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column("sender", sa.String(length=180), primary_key=False, nullable=False),
        sa.Column("project", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("asset_id", sa.String(length=32), primary_key=False, nullable=False),
        sa.Column("title", sa.String(length=160), primary_key=False, nullable=False),
        sa.Column("body", sa.Text(), primary_key=False, nullable=False),
        if_not_exists=True,
    )
    op.create_table(
        "notice_reads",
        sa.Column("notice_id", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("subject", sa.String(length=180), primary_key=True, nullable=False),
        if_not_exists=True,
    )
    op.create_table(
        "invocation_logs",
        sa.Column("request_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column("actor", sa.String(length=180), primary_key=False, nullable=False),
        sa.Column("owner", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("project", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("asset_id", sa.String(length=32), primary_key=False, nullable=False),
        sa.Column("environment", sa.String(length=16), primary_key=False, nullable=False),
        sa.Column("method", sa.String(length=16), primary_key=False, nullable=False),
        sa.Column("operation", sa.Text(), primary_key=False, nullable=False),
        sa.Column("status", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("duration_ms", sa.Integer(), primary_key=False, nullable=False),
        if_not_exists=True,
    )
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.String(length=140), primary_key=True, nullable=False),
        sa.Column("asset_id", sa.String(length=32), primary_key=False, nullable=False),
        sa.Column("project", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("environment", sa.String(length=16), primary_key=False, nullable=False),
        sa.Column("threshold", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("minutes", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("stop", sa.Boolean(), primary_key=False, nullable=False),
        sa.Column("enabled", sa.Boolean(), primary_key=False, nullable=False),
        sa.Column("window", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("calls", sa.Integer(), primary_key=False, nullable=False),
        if_not_exists=True,
    )


def downgrade():
    for table in ("alert_rules", "invocation_logs", "notice_reads", "notices", "portal_members"):
        op.drop_table(table, if_exists=True)
    op.drop_column("assets", "removed_at")
