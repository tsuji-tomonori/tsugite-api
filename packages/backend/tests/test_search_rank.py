import json

from app.apis.catalog.search_rank import rank_assets
from tsugite_db.models import Asset


def product(key, name, summary="", tag="", definition=""):
    spec = {
        "openapi": "3.1.0",
        "info": {"title": name, "version": "1"},
        "paths": {"/lookup": {"get": {"tags": [tag] if tag else [], "operationId": "readRecord"}}},
        "tags": [{"name": tag, "description": definition}] if tag else [],
    }
    return Asset(id=key, name=name, summary=summary, owner="sample", spec=json.dumps(spec))


def test_hybrid_retrieval():
    stock = product("b", "倉庫在庫", "棚卸の残数を調べる")
    exact = product("a", "Inventory Ledger", "会計上の棚卸資産")
    other = product("c", "請求照会", "インボイスを照合する")
    rows = [stock, other, exact]
    assert rank_assets(rows, "ＩＮＶＥＮＴＯＲＹ", "lexical") == [exact]
    assert set(rank_assets(rows, "inventory", "semantic")) == {stock, exact}
    assert rank_assets(rows, "inventory") == [exact, stock]
    assert rank_assets(reversed(rows), "inventory") == [exact, stock]
    assert rank_assets(rows, "天体観測") == []
    assert set(rank_assets(rows, "readRecord", "lexical")) == set(rows)
    assert rank_assets(rows, " ") == sorted(rows, key=lambda a: (a.name, a.id))


def test_visible_openapi_tags_supply_custom_meaning():
    glossary = product(
        "a", "炉の管理", tag="heat-treatment", definition="製造工程で金属を焼きなます作業"
    )
    oven = product("b", "炉温照会", tag="heat-treatment")
    customer = product("c", "顧客台帳")
    assert rank_assets([glossary, oven, customer], "焼きなます", "lexical") == []
    assert set(rank_assets([glossary, oven, customer], "焼きなます")) == {glossary, oven}
    # Restricted tag definitions cannot expand a query in a different audience.
    assert rank_assets([oven, customer], "焼きなます") == []
