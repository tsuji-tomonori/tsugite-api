# 商品の停止状態に対応するDBスキーマへ移行する。
"""Store the administrator's invocation suspension independently of publication."""

import sqlalchemy as sa
from alembic import op
from tsugite_db.migration_columns import column_names

revision = "009"
down_revision = "008"


def upgrade() -> None:
    if "suspended" not in column_names(op.get_bind(), "assets"):
        op.add_column("assets", sa.Column("suspended", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "suspended")
