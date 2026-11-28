"""API呼び出しログの出力に、記録時の重大度と対処方法を残せるようにする。"""

import sqlalchemy as sa
from alembic import op
from tsugite_db.migration_columns import column_names

revision = "008"
down_revision = "007"


def upgrade():
    if "diagnostics" not in column_names(op.get_bind(), "invocation_logs"):
        op.add_column("invocation_logs", sa.Column("diagnostics", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("invocation_logs", "diagnostics")
