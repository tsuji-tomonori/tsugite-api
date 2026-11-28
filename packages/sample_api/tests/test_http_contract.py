"""公開YAMLを基準に商品ごとの各応答を照合する。"""

import sqlite3
from unittest.mock import Mock

import pytest
import yaml
from fastapi.testclient import TestClient
from sample_api.database import SampleDatabase
from sample_api.main import PRODUCTS, app

from packages.tools.design.sample_openapi import OUTPUT
from tests.support.http_contract import Contract, validation_request


@pytest.mark.parametrize(
    "slug",
    [
        pytest.param(
            slug, id=slug, marks=pytest.mark.case_detail(f"商品「{product.title}」の公開契約を照合する")
        )
        for slug, product in PRODUCTS.items()
    ],
)
def test_product_http_contract(slug, monkeypatch):
    """掲載中の商品の各操作で、正常・入力不正・該当なし・DB障害の実応答を公開仕様と照合する。"""
    contract = Contract(yaml.safe_load((OUTPUT / f"{slug}.yaml").read_text()))
    paths = contract.document["paths"]
    base = "/" + slug
    with TestClient(app, raise_server_exceptions=False) as client:
        collection = next(path for path in paths if "{" in path).rsplit("/", 1)[0]
        rows = client.get(base + collection).raise_for_status().json()
        row = (rows["items"] if isinstance(rows, dict) else rows)[0]
        for path, methods in paths.items():
            for method, operation in methods.items():
                url = base + path.format(**row)
                args = {"json": {"units": 7}} if "requestBody" in operation else {}
                response = client.request(method, url, **args)
                assert response.status_code == 200, (slug, method, path)
                contract.check(path, method, response)
                if "404" in operation["responses"]:
                    params = {p["name"]: "UNKNOWN" for p in operation.get("parameters", [])}
                    missing = base + path.format(**params)
                    query = {"on_or_after": "2099-01-01"} if path == "/calendar/next" else {}
                    response = client.request(method, missing, params=query)
                    assert response.status_code == 404, (slug, path)
                    contract.check(path, method, response)
                if "422" in operation["responses"]:
                    invalid, kwargs = validation_request(path, operation)
                    response = client.request(method, base + invalid, **kwargs)
                    assert response.status_code == 422, (slug, path)
                    contract.check(path, method, response)
                with monkeypatch.context() as patch:
                    failed_db = Mock()
                    failed_db.execute.side_effect = sqlite3.OperationalError("テスト用のDB障害")
                    patch.setattr(SampleDatabase, "connection", property(lambda self: failed_db))
                    response = client.request(method, url, **args)
                    assert response.status_code == 500, (slug, path)
                    failed_db.execute.assert_called_once()
                    contract.check(path, method, response)
