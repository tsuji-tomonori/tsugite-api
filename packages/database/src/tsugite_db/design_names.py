# 宣言内のコメントから設計書に載せる業務名を取得する。
"""Read business names from mapped classes and match them to SQLAlchemy metadata."""

import ast
from functools import cache
from pathlib import Path

from .source_docs import read_source


#: データベース移行版管理
def version_table():
    """適用済みマイグレーション版

    Alembicが適用済みとして管理している最新のマイグレーション版を、移行履歴の先端ごとに1件保存します。
    """
    from alembic.migration import MigrationContext

    table = MigrationContext.configure(dialect_name="postgresql").impl.version_table_impl(
        version_table="alembic_version", version_table_schema=None, version_table_pk=True
    )
    #: 適用済みのマイグレーション版番号
    column = table.c.version_num
    return table, column


def design_tables():
    from sqlalchemy import Table

    from .models import Base

    tables = [
        (m.local_table, m.class_.__name__)
        for m in Base.registry.mappers
        if isinstance(m.local_table, Table)
    ]
    return sorted([*tables, (version_table()[0], None)], key=lambda row: row[0].name)


def table_entry(source, node, columns):
    record, grain = (ast.get_docstring(node) or "").split("\n\n", 1)
    return {"table": source.label(node), "record": record, "grain": grain, "columns": columns}


@cache
def table_names():
    import inspect

    from sqlalchemy import Table

    from .models import Base

    entries = {}
    for mapper in Base.registry.mappers:
        if not isinstance(mapper.local_table, Table):
            continue
        cls = mapper.class_
        source = read_source(Path(inspect.getfile(cls)))
        node = next(
            n for n in source.tree.body if isinstance(n, ast.ClassDef) and n.name == cls.__name__
        )
        labels = source.fields(node)
        columns = {c.name: labels[mapper.get_property_by_column(c).key] for c in mapper.local_table.c}
        entries[mapper.local_table.name] = table_entry(source, node, columns)

    source = read_source(Path(__file__))
    factory = next(
        n
        for n in source.tree.body
        if isinstance(n, ast.FunctionDef) and n.name == version_table.__name__
    )
    table, column = version_table()
    definition = next(
        n
        for n in factory.body
        if isinstance(n, ast.Assign)
        and isinstance(n.value, ast.Attribute)
        and n.value.attr == column.name
    )
    entries[table.name] = table_entry(source, factory, {column.name: source.label(definition)})
    return entries
