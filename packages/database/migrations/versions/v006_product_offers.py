"""環境別の提供条件、申請の証跡、公開後に変更できないリリースを保存できるようにする。"""

import sqlalchemy as sa
from alembic import op
from tsugite_db.migration_columns import column_names

revision = "006"
down_revision = "005"


def upgrade():
    for table, fields in (
        ("assets", (("offers", sa.Text()), ("release_note", sa.Text()))),
        ("access_rights", (("submission", sa.Text()), ("stage", sa.String(80)))),
    ):
        existing = column_names(op.get_bind(), table)
        for name, kind in fields:
            if name not in existing:
                op.add_column(table, sa.Column(name, kind))
    op.create_table(
        "spec_releases",
        sa.Column("asset_id", sa.String(32), primary_key=True),
        sa.Column("number", sa.Integer(), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("manifest", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        if_not_exists=True,
    )


def downgrade():
    op.drop_table("spec_releases", if_exists=True)
    for table, names in (
        ("assets", ("offers", "release_note")),
        ("access_rights", ("submission", "stage")),
    ):
        for name in names:
            op.drop_column(table, name)
