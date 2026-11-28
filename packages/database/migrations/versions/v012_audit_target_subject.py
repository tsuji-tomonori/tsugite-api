"""利用者に対する操作の監査記録に、対象者の固定識別子を追加する。"""

import sqlalchemy as sa
from alembic import op
from tsugite_db.migration_columns import column_names

revision = "012"
down_revision = "011"


def upgrade() -> None:
    if "target_subject" not in column_names(op.get_bind(), "audit_events"):
        op.add_column("audit_events", sa.Column("target_subject", sa.String(180), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_events", "target_subject")
