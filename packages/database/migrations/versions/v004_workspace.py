# 所属組織に対応するDBスキーマへ移行する。
"""Directory, scoped credentials, subscription principals and historical organization attribution."""

import sqlalchemy as sa
from alembic import op
from tsugite_db.migration_columns import column_names

revision = "004"
down_revision = "003"


def upgrade():
    existing = column_names(op.get_bind(), "assets")
    if "policy" not in existing:
        op.add_column("assets", sa.Column("policy", sa.Text(), nullable=True))
    existing = column_names(op.get_bind(), "access_rights")
    if "applicant" not in existing:
        op.add_column("access_rights", sa.Column("applicant", sa.String(180), nullable=True))
    if "subject" not in existing:
        op.add_column("access_rights", sa.Column("subject", sa.String(180), nullable=True))
    if "decision_note" not in existing:
        op.add_column("access_rights", sa.Column("decision_note", sa.Text(), nullable=True))
    existing = column_names(op.get_bind(), "invocation_logs")
    if "key_id" not in existing:
        op.add_column("invocation_logs", sa.Column("key_id", sa.String(32), nullable=True))
    op.create_table(
        "directory_tree",
        sa.Column("id", sa.String(length=12), primary_key=True, nullable=False),
        sa.Column("units", sa.Text(), primary_key=False, nullable=False),
        sa.Column("revision", sa.Integer(), primary_key=False, nullable=False),
        if_not_exists=True,
    )
    op.create_table(
        "affiliations",
        sa.Column("subject", sa.String(length=180), primary_key=True, nullable=False),
        sa.Column("unit_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=120), primary_key=False, nullable=False),
        sa.Column("leader", sa.Boolean(), primary_key=False, nullable=False),
        sa.Column("active", sa.Boolean(), primary_key=False, nullable=False),
        if_not_exists=True,
    )
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("digest", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("project", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("creator", sa.String(length=180), primary_key=False, nullable=False),
        sa.Column("name", sa.String(length=120), primary_key=False, nullable=False),
        sa.Column("kind", sa.String(length=12), primary_key=False, nullable=False),
        sa.Column("scopes", sa.Text(), primary_key=False, nullable=False),
        sa.Column("revoked", sa.Boolean(), primary_key=False, nullable=False),
        sa.Column("revision", sa.Integer(), primary_key=False, nullable=False),
        if_not_exists=True,
    )
    op.create_table(
        "invocation_units",
        sa.Column("request_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("unit_id", sa.String(length=64), primary_key=True, nullable=False),
        if_not_exists=True,
    )


def downgrade():
    op.drop_table("invocation_units", if_exists=True)
    op.drop_table("api_keys", if_exists=True)
    op.drop_table("affiliations", if_exists=True)
    op.drop_table("directory_tree", if_exists=True)
    op.drop_column("assets", "policy")
    op.drop_column("access_rights", "applicant")
    op.drop_column("access_rights", "subject")
    op.drop_column("access_rights", "decision_note")
    op.drop_column("invocation_logs", "key_id")
