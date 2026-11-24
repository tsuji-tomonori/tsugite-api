# 公開されたOpenAPIと操作契約から、クライアントが構成する呼び出しと表示用コマンドを検証する。
import json
import shlex
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

Module = Callable[[str], Any]


@pytest.mark.parametrize(("asset", "identifier"), [
    pytest.param({"slug": "stock-lookup", "id": "old-id"}, "stock-lookup", id="slug",
                 marks=pytest.mark.case_detail("識別名を指定した商品は識別名で呼び出す")),
    pytest.param({"id": "old-id", "slug": None}, "old-id", id="legacy",
                 marks=pytest.mark.case_detail("識別名のない既存商品は従来の識別子で呼び出す")),
])
def test_gateway_url_uses_product_identity(portal_module: Module, asset: dict[str, Any], identifier: str) -> None:
    """ゲートウェイの呼び出し先は商品の識別名、承認環境、利用プロジェクトで決まる。"""
    path = portal_module("apis.client").invocation_path(asset, "sandbox", "finance")
    assert path.rstrip("/") == f"/api/invoke/{identifier}/sandbox/finance"


def test_openapi_location_uses_path_and_query(portal_module: Module) -> None:
    """OpenAPIのパス・クエリを別々にエンコードし、任意の未入力値を送信対象から外す。"""
    docs = portal_module("components.api_docs")
    params = [
        {"in": "path", "name": "sku", "required": True, "schema": {"type": "string"}},
        {"in": "query", "name": "warehouse", "schema": {"type": "string"}},
        {"in": "query", "name": "region", "schema": {"type": "string"}},
    ]
    location = docs.build_location({}, "/items/{sku}", params, {0: "A/B", 1: "東京 & 横浜", 2: ""})
    parsed = urlsplit(location)
    assert parsed.path == "/items/A%2FB"
    assert parse_qs(parsed.query, keep_blank_values=True) == {"warehouse": ["東京 & 横浜"]}


def test_openapi_schema_names_and_request_parameters(portal_module: Module) -> None:
    """OpenAPI内部参照の型、パス共通の入力、個別操作で上書きした入力を正しく解決する。"""
    fields = portal_module("content.openapi_fields")
    sku = {"name": "sku", "in": "path", "required": True, "schema": {"type": "string"}}
    initial = {"name": "count", "in": "query", "schema": {"type": "integer"}}
    modified = {**initial, "required": True}
    spec = {"components": {"parameters": {"Sku": sku}, "schemas": {"StockItem": {"type": "object", "title": "在庫"}}}}
    item = {"parameters": [{"$ref": "#/components/parameters/Sku"}, initial]}
    operation = {"parameters": [modified]}
    assert fields.resolve(spec, {"$ref": "#/components/schemas/StockItem"}) == {"type": "object", "title": "在庫"}
    resolved = fields.parameters(spec, item, operation)
    assert {p["name"]: p for p in resolved} == {"sku": sku, "count": modified}
    assert len(resolved) == 2


def test_curl_copy_preserves_request_and_uses_shell_token(portal_module: Module) -> None:
    """コピー用curlは入力したURL・JSON本文・ヘッダーを保持し、アクセストークンをシェル変数で参照する。"""
    docs = portal_module("components.api_docs")
    url = "https://portal.example/api/invoke/stock/production/finance/items?limit=2"
    body = json.dumps({"item": "担当者's 倉庫"}, ensure_ascii=False)
    options = {"method": "POST", "headers": {"Authorization": "Bearer private-example",
                                              "Content-Type": "application/json"}, "body": body}
    command = docs.curl_command(url, options)
    args = shlex.split(command)
    assert args[0] == "curl"
    assert url in args and body in args and "POST" in args
    assert "Content-Type: application/json" in args
    assert "private-example" not in command
    assert "ACCESS_TOKEN" in command


@pytest.mark.parametrize(("method", "body"), [
    pytest.param("GET", "", id="read", marks=pytest.mark.case_detail("GETで入力したヘッダーとURLを利用する")),
    pytest.param("PATCH", '{"stock":12}', id="update",
                 marks=pytest.mark.case_detail("PATCHでは本文と接続先専用のヘッダーを送る")),
])
def test_manual_request_uses_only_destination_credentials(portal_module: Module, method: str, body: str) -> None:
    """URLの直接指定では入力したヘッダーと本文だけを使い、ポータルの資格情報を付けずに送る。"""
    manual = portal_module("apis.manual")
    options = manual.request_options("https://inventory.example/items", method, "X-Trace: 棚卸\nAccept: application/json", body)
    assert options["method"] == method
    assert options["headers"] == {"x-trace": "棚卸", "accept": "application/json"}
    assert options["credentials"] == "omit"
    assert options.get("body", "") == body


@pytest.mark.parametrize(("method", "headers", "body", "reason"), [
    pytest.param("GET", "", "quantity=3", "本文", id="get-body",
                 marks=pytest.mark.case_detail("GETに本文を指定したら本文のエラーを示す")),
    pytest.param("POST", "X-Trace", "", "ヘッダー", id="incomplete-header",
                 marks=pytest.mark.case_detail("ヘッダーの値を区切れない入力では形式を案内する")),
])
def test_client_explains_invalid_input(portal_module: Module, method: str, headers: str, body: str, reason: str) -> None:
    """指定したメソッドやヘッダーに合わない入力では、送信前に誤りのある項目を示す。"""
    manual = portal_module("apis.manual")
    with pytest.raises(portal_module("apis.client").InputError, match=reason):
        manual.request_options("https://inventory.example/items", method, headers, body)


@pytest.mark.parametrize(("schema_type", "style", "explode", "entered", "query"), [
    pytest.param("array", "form", True, '["A","B"]', {"q": ["A", "B"]}, id="repeated",
                 marks=pytest.mark.case_detail("展開する配列は同名のクエリ項目を繰り返す")),
    pytest.param("array", "pipeDelimited", False, '["A","B"]', {"q": ["A|B"]}, id="pipe",
                 marks=pytest.mark.case_detail("縦棒区切りの配列は一つの項目にまとめる")),
    pytest.param("array", "spaceDelimited", False, '["A","B"]', {"q": ["A B"]}, id="space",
                 marks=pytest.mark.case_detail("空白区切りの配列は一つの項目にまとめる")),
    pytest.param("object", "form", False, '{"bin":3,"ready":true}', {"q": ["bin,3,ready,true"]}, id="flat",
                 marks=pytest.mark.case_detail("展開しないオブジェクトはキーと値を順番に並べる")),
    pytest.param("object", "form", True, '{"bin":3,"ready":true}', {"bin": ["3"], "ready": ["true"]}, id="expanded",
                 marks=pytest.mark.case_detail("展開するオブジェクトはキー別のクエリにする")),
    pytest.param("object", "deepObject", True, '{"bin":3,"ready":false}', {"q[bin]": ["3"], "q[ready]": ["false"]},
                 id="deep", marks=pytest.mark.case_detail("入れ子のオブジェクトは項目名とキーを角括弧で結ぶ")),
])
def test_openapi_query_serialization(portal_module: Module, schema_type: str, style: str, explode: bool,
                                    entered: str, query: dict[str, list[str]]) -> None:
    """配列・オブジェクトの入力をOpenAPIに指定したシリアライズ形式と展開規則でURLに組み込む。"""
    param = {"name": "q", "in": "query", "style": style, "explode": explode, "schema": {"type": schema_type}}
    url = portal_module("components.api_docs").build_location({}, "/stock", [param], {0: entered})
    assert parse_qs(urlsplit(url).query) == query


@pytest.mark.parametrize(("schema_type", "entered", "expected"), [
    pytest.param("array", '["A","B"]', "A,B", id="array",
                 marks=pytest.mark.case_detail("パスの配列は要素をコンマで区切る")),
    pytest.param("object", '{"warehouse":"A","bin":2}', "warehouse=A,bin=2", id="object",
                 marks=pytest.mark.case_detail("展開したパスのオブジェクトはキーと値を等号で結ぶ")),
])
def test_openapi_path_structured_parameters(portal_module: Module, schema_type: str, entered: str, expected: str) -> None:
    """構造を持つ必須パスパラメータをOpenAPIのsimple形式で組み込む。"""
    param = {"name": "loc", "in": "path", "required": True, "style": "simple", "explode": True, "schema": {"type": schema_type}}
    url = portal_module("components.api_docs").build_location({}, "/stock/{loc}", [param], {0: entered})
    assert url == f"/stock/{expected}"


@pytest.mark.parametrize(("entered", "detail"), [
    pytest.param('{"id":"A"}', "array", id="wrong-type",
                 marks=pytest.mark.case_detail("配列入力にオブジェクトを指定したときは必要な型を案内する")),
    pytest.param("[", "JSON", id="malformed",
                 marks=pytest.mark.case_detail("配列の記述が不完全なときはJSON形式を案内する")),
])
def test_openapi_reports_invalid_structured_input(portal_module: Module, entered: str, detail: str) -> None:
    """配列を受け取る操作に無効な入力があれば、送信前に項目名と必要な形式を示す。"""
    docs = portal_module("components.api_docs")
    param = {"name": "warehouses", "in": "query", "schema": {"type": "array"}}
    with pytest.raises(portal_module("apis.client").InputError) as error:
        docs.build_location({}, "/stock", [param], {0: entered})
    assert "warehouses" in str(error.value) and detail in str(error.value)
