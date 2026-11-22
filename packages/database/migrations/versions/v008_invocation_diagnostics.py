"""Keep the original severity and remediation on invocation log exports."""

import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "007"


def upgrade():
    columns = sa.inspect(op.get_bind()).get_columns("invocation_logs")
    if all(column["name"] != "diagnostics" for column in columns):
        op.add_column("invocation_logs", sa.Column("diagnostics", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("invocation_logs", "diagnostics")
