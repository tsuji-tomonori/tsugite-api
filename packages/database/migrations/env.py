# Alembicの接続とマイグレーション実行環境を構成する。
from alembic import context
from alembic.ddl.postgresql import PostgresqlImpl
from tsugite_db.models import Base
from tsugite_db.session import engine


class DsqlImpl(PostgresqlImpl):
    __dialect__ = "auroradsql"
    transactional_ddl = False


with engine().connect() as connection:
    # DSQL permits one DDL statement per transaction. The frozen revisions
    # below use idempotent DDL, so an interrupted upgrade can be resumed.
    if connection.dialect.name == "auroradsql":
        connection.execution_options(isolation_level="AUTOCOMMIT")
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        dialect_name="postgresql"
        if connection.dialect.name == "auroradsql"
        else connection.dialect.name,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()
