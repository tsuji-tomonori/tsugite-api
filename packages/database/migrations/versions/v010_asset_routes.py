# 商品の呼び出し名に対応するDBスキーマへ移行する。
"""Reserve a unique invocation name for each catalog product."""

import sqlalchemy as sa
from alembic import op

revision = "010"
down_revision = "009"


def upgrade() -> None:
    op.create_table(
        "asset_routes",
        sa.Column("asset_id", sa.String(32), primary_key=True),
        sa.Column("slug", sa.String(63), nullable=False, unique=True),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("asset_routes", if_exists=True)
