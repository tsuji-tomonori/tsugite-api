from unittest.mock import Mock, patch

from tsugite_db.migration_columns import column_names


def test_dsql_column_names_use_the_system_catalog():
    """Aurora DSQL では公開スキーマの現行カラム名をシステムカタログから取得する"""
    connection = Mock()
    connection.dialect.name = "auroradsql"
    connection.scalars.return_value = ["id", "name"]

    with patch("tsugite_db.migration_columns.inspect") as inspect:
        assert column_names(connection, "assets") == {"id", "name"}
    inspect.assert_not_called()
    query, parameters = connection.scalars.call_args.args
    assert "pg_catalog.pg_attribute" in query.text
    assert "n.nspname = 'public'" in query.text
    assert "a.attnum > 0 AND NOT a.attisdropped" in query.text
    assert parameters == {"table": "assets"}
