"""Short-lived token clients, renewal schedules and nested authority bounds."""

import time

import sqlalchemy as sa
from alembic import op
from tsugite_db.migration_columns import column_names

revision = "005"
down_revision = "004"


def upgrade():
    columns = column_names(op.get_bind(), "api_keys")
    for name, kind in (("mode", sa.String(10)), ("config", sa.Text()), ("created", sa.Integer())):
        if name not in columns:
            op.add_column("api_keys", sa.Column(name, kind, nullable=True))
    op.get_bind().execute(
        sa.text("UPDATE api_keys SET created = :stamp WHERE created IS NULL"),
        {"stamp": int(time.time())},
    )
    op.create_table(
        "credential_leases",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("issued", sa.Integer(), nullable=False),
        sa.Column("expires", sa.Integer(), nullable=False),
        sa.Column("refresh_at", sa.Integer(), nullable=False),
        sa.Column("nonce", sa.String(32), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        if_not_exists=True,
    )
    op.create_table(
        "credential_rules",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("limit_minutes", sa.Integer()),
        sa.Column("ops", sa.Text()),
        sa.Column("revision", sa.Integer(), nullable=False),
        if_not_exists=True,
    )


def downgrade():
    op.drop_table("credential_rules", if_exists=True)
    op.drop_table("credential_leases", if_exists=True)
    for col in ("created", "config", "mode"):
        op.drop_column("api_keys", col)
