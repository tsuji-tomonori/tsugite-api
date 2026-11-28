"""公開承認の進捗と登録時の責任者を保存する。"""

import sqlalchemy as sa
from alembic import op
from tsugite_db.migration_columns import column_names

revision = "013"
down_revision = "012"


def upgrade() -> None:
    existing = column_names(op.get_bind(), "assets")
    for name, datatype in (("publication_request", sa.Text()), ("responsible", sa.String(180))):
        if name not in existing:
            op.add_column("assets", sa.Column(name, datatype, nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "responsible")
    op.drop_column("assets", "publication_request")
