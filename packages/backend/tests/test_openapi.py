import pytest
from app.core.openapi import path_items


def test_resolves_path_item_references_in_order():
    """内部参照の連鎖とJSON Pointerのエスケープを解決し、パス順を保つ。"""
    operation = {"get": {"operationId": "readStock"}}
    spec = {
        "paths": {"/inventory": {"$ref": "#/x-start"}, "/orders": {"post": {}}},
        "x-start": {"$ref": "#/components/pathItems/a~1b~0%20c"},
        "components": {"pathItems": {"a/b~ c": operation}},
    }
    assert list(path_items(spec)) == [("/inventory", operation), ("/orders", {"post": {}})]


@pytest.mark.parametrize(
    "item",
    [
        pytest.param(
            {"$ref": "#/x-loop"}, id="cycle", marks=pytest.mark.case_detail("自分自身を参照している")
        ),
        pytest.param(
            {"$ref": "#/x-unknown"}, id="missing", marks=pytest.mark.case_detail("参照先が存在しない")
        ),
        pytest.param(
            {"$ref": "https://example.test/api.json#/paths"},
            id="remote",
            marks=pytest.mark.case_detail("外部ドキュメントを参照している"),
        ),
        pytest.param([], id="invalid", marks=pytest.mark.case_detail("パス項目が配列になっている")),
    ],
)
def test_skips_invalid_path_item_without_losing_valid_paths(item):
    """解決できないパスと拡張項目を飛ばし、有効なパスを返す。"""
    spec = {"paths": {"/invalid": item, "x-extra": {}, "/valid": {"get": {}}}, "x-loop": item}
    assert list(path_items(spec)) == [("/valid", {"get": {}})]
