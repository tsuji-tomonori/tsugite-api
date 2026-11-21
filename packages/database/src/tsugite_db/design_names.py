"""Business names of database tables, record types and columns."""

import tomllib
from functools import cache
from pathlib import Path


@cache
def table_names():
    with Path(__file__).with_name("names.toml").open("rb") as file:
        return tomllib.load(file)


def design_tables():
    from alembic.migration import MigrationContext
    from sqlalchemy import Table

    from .models import Base

    tables = [
        (m.local_table, m.class_.__name__)
        for m in Base.registry.mappers
        if isinstance(m.local_table, Table)
    ]
    version_table = MigrationContext.configure(dialect_name="postgresql").impl.version_table_impl(
        version_table="alembic_version", version_table_schema=None, version_table_pk=True
    )
    return sorted([*tables, (version_table, None)], key=lambda row: row[0].name)
