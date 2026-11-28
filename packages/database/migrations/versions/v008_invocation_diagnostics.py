# API呼び出しの診断情報に対応するDBスキーマへ移行する。
"""Keep the original severity and remediation on invocation log exports."""

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
