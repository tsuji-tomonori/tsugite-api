from alembic import context
from app.db.models import Base
from app.db.session import engine

from alembic.ddl.postgresql import PostgresqlImpl


class DsqlImpl(PostgresqlImpl):
    __dialect__ = "auroradsql"
    transactional_ddl = False


with engine().connect() as connection:
    # DSQL permits one DDL statement per transaction. The frozen revisions
    # below use idempotent DDL, so an interrupted upgrade can be resumed.
    if connection.dialect.name == "auroradsql":
        connection.execution_options(isolation_level="AUTOCOMMIT")
    context.configure(connection=connection, target_metadata=Base.metadata,
                      dialect_name="postgresql" if connection.dialect.name == "auroradsql" else connection.dialect.name,
                      transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()
