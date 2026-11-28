# 商品ごとのAPI操作・スキーマ・ヘルスチェックを検証する。
import json

import pytest
from fastapi.testclient import TestClient
from openapi_spec_validator import validate
from sample_api.main import PRODUCTS, app, handler

from packages.tools.demo.seed_marketplace import CATALOG, offer
from packages.tools.design.sample_openapi import OUTPUT, generate


def test_generated_product_contracts(tmp_path):
    """全商品の出品仕様がFastAPIと一致し、再生成した各YAMLを同じ内容で公開できる。"""
    generate(tmp_path)
    assert set(PRODUCTS) == {p["slug"] for p in CATALOG}
    assert len(PRODUCTS) == 24
    assert sorted(p.name for p in tmp_path.glob("*.yaml")) == sorted(
        p.name for p in OUTPUT.glob("*.yaml")
    )
    for product in CATALOG:
        slug = product["slug"]
        contract = offer(product)["spec"]
        validate(contract)
        assert PRODUCTS[slug].openapi() == contract
        assert product["name"] == contract["info"]["title"]
        assert (tmp_path / f"{slug}.yaml").read_bytes() == (OUTPUT / f"{slug}.yaml").read_bytes()


@pytest.mark.usefixtures("lambda_event_loop")
def test_each_product_operation_through_lambda():
    """全商品で5つの業務操作とヘルスチェックを実行し、商品境界とLambda応答を照合する。"""
    client = TestClient(app)
    primary_paths = set()
    for product in CATALOG:
        listing = offer(product)
        base = listing["base_path"]
        paths = listing["spec"]["paths"]
        collection = next(path for path, methods in paths.items() if "{" in path).rsplit("/", 1)[0]
        assert collection not in primary_paths
        primary_paths.add(collection)
        listing_rows = client.get(base + collection).raise_for_status().json()
        rows = listing_rows["items"] if isinstance(listing_rows, dict) else listing_rows
        operations = [(method, path) for path, methods in paths.items() for method in methods]
        assert len(operations) == 6 and ("get", "/health") in operations
        for method, path in operations:
            path = base + path.format(**rows[0])
            result = handler(
                {
                    "version": "2.0",
                    "rawPath": path,
                    "rawQueryString": "",
                    "headers": {"content-type": "application/json"},
                    "requestContext": {
                        "http": {"method": method.upper(), "path": path, "sourceIp": "127.0.0.1"}
                    },
                    "body": '{"units":7}' if method == "post" else None,
                },
                None,
            )
            assert result["statusCode"] == 200, (path, result)
            data = json.loads(result["body"])
            assert data, path
            if path.endswith("/health"):
                assert data == {"status": "ok"}
            if method == "post":
                assert data["units"] == 7
        assert client.get(base + collection + "/UNKNOWN").status_code == 404
    assert client.get("/parcel-tracking/items").status_code == 404
    assert client.get("/warehouse-stock/low-stock?maximum=0").json() == []


def test_catalog_business_operations_are_distinct():
    """共通ヘルスチェックを除く操作と詳細レスポンスの項目で、全サンプル商品を区別できる。"""
    operations = set()
    detail_fields = set()
    for product in CATALOG:
        spec = offer(product)["spec"]
        paths = spec["paths"]
        business = {(path, verb) for path in paths if path != "/health" for verb in paths[path]}
        assert len(business) == 5 and business.isdisjoint(operations), product["slug"]
        operations.update(business)
        detail = next(methods["get"] for path, methods in paths.items() if "{" in path)
        schema = detail["responses"]["200"]["content"]["application/json"]["schema"]
        model = schema["$ref"].rsplit("/", 1)[-1]
        fields = frozenset(spec["components"]["schemas"][model]["properties"])
        assert fields not in detail_fields, product["slug"]
        detail_fields.add(fields)
