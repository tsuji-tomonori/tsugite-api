# スキーマ更新前に既存の列を取得する。
"""Read the column names needed for idempotent schema upgrades."""

from sqlalchemy import Connection, inspect, text


def column_names(connection: Connection, table: str) -> set[str]:
    if connection.dialect.name != "auroradsql":
        return {column["name"] for column in inspect(connection).get_columns(table)}

    # The DSQL dialect's reflection query omits fields required by SQLAlchemy.
    # Migrations only need names of live columns in the catalog's public schema.
    names = connection.scalars(
        text(
            "SELECT a.attname FROM pg_catalog.pg_attribute AS a "
            "JOIN pg_catalog.pg_class AS c ON c.oid = a.attrelid "
            "JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = :table "
            "AND a.attnum > 0 AND NOT a.attisdropped"
        ),
        {"table": table},
    )
    return set(names)
