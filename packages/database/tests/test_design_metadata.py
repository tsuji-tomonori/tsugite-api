"""テーブル定義とPython宣言に付いた業務名の対応を検証する。"""

import pytest
from tsugite_db.design_names import design_tables, table_names
from tsugite_db.source_docs import SourceDocs, read_source


def test_every_column_is_documented_including_schema_version():
    """実際のテーブルと列に業務名が対応し、Alembicの内部テーブルにも説明がある。"""
    names = table_names()
    tables = design_tables()
    assert [table.name for table, _ in tables] == sorted(names)
    for table, _ in tables:
        assert set(names[table.name]["columns"]) == set(table.columns.keys())
        assert all(names[table.name]["columns"].values())
    assert names["alembic_version"]["columns"] == {"version_num": "適用済みのマイグレーション版番号"}


def test_labels_follow_the_first_literal_on_each_annotated_line(tmp_path):
    """コメントの次の行にある最初の文字列だけを業務名に対応付ける。"""
    source = SourceDocs('#: 商品\nfields = {"asset": "ignored"}\nmore = "other"\n')
    assert source.literal_labels(source.tree) == {"asset": "商品"}
    with pytest.raises(ValueError, match="Pythonソース"):
        read_source(tmp_path / "metadata.json")
