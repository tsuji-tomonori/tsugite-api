"""Allow multiple APIs to share one team-owned HTTPS origin."""

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"


def upgrade():
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("assets")}
    if "base_path" not in existing:
        op.add_column("assets", sa.Column("base_path", sa.String(300), nullable=True))


def downgrade():
    op.drop_column("assets", "base_path")
