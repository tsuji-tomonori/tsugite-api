# APIのベースパスに対応するDBスキーマへ移行する。
"""Allow multiple APIs to share one team-owned HTTPS origin."""

import sqlalchemy as sa
from alembic import op
from tsugite_db.migration_columns import column_names

revision = "002"
down_revision = "001"


def upgrade():
    existing = column_names(op.get_bind(), "assets")
    if "base_path" not in existing:
        op.add_column("assets", sa.Column("base_path", sa.String(300), nullable=True))


def downgrade():
    op.drop_column("assets", "base_path")
