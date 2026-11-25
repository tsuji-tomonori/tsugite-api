# 公開操作のエラー経路を実際のHTTPリクエストで確認する。
from unittest.mock import Mock

from fastapi.routing import APIRoute, iter_route_contexts
from tsugite_db.session import session

from tests.support.catalog import FORM, headers
from tests.support.http_contract import validation_request


def test_backend_contract_responses(portal, monkeypatch):
    """公開操作ごとに認証・入力検査・内部障害を再現し、契約のステータスと本文を返す。"""
    app = portal.app
    document = app.openapi()
    identity = headers(portal, "admin")
    routes = {
        r.path_format: r
        for r in iter_route_contexts(app.routes)
        if isinstance(r.original_route, APIRoute)
    }
    for path, methods in document["paths"].items():
        for method, operation in methods.items():
            url = path.format(
                **{p["name"]: "test" for p in operation.get("parameters", []) if p["in"] == "path"}
            )
            if operation.get("security"):
                assert portal.request(method, url).status_code == 401, (method, path)
            if "422" in operation["responses"]:
                invalid, kwargs = validation_request(path, operation)
                request_headers = {**identity, **kwargs.pop("headers", {})}
                assert (
                    portal.request(method, invalid, headers=request_headers, **kwargs).status_code == 422
                ), (method, path)
            with monkeypatch.context() as patch:
                patch.setenv("AWS_LAMBDA_FUNCTION_NAME", "contract-test")
                patch.setenv("ORIGIN_SECRET", "local-test")
                assert portal.request(method, url).status_code == 403, (method, path)

            def unavailable():
                raise RuntimeError("テスト用の内部障害")

            with monkeypatch.context() as patch:
                if path in {"/api/config", "/api/health"}:
                    patch.setattr(routes[path].dependant, "call", unavailable)
                else:
                    patch.setitem(app.dependency_overrides, session, unavailable)
                result = portal.request(method, url, headers=identity)
                assert result.status_code == 500, (method, path, result.status_code)
                assert result.json()["error_code"] == "INTERNAL_ERROR"


def test_catalog_search_failure(portal, monkeypatch):
    """カタログ検索中に内部障害が起きるとリクエストIDと共通エラーコードを受け取れる。"""
    search = Mock(side_effect=RuntimeError("検索障害"))
    monkeypatch.setattr("app.apis.catalog.catalog.collection", search)
    response = portal.get("/api/apis", headers=headers(portal, "consumer"))
    search.assert_called_once()
    assert response.status_code == 500
    assert response.headers["X-Request-ID"]
    assert response.json()["error_code"] == "INTERNAL_ERROR"


def test_health_config_and_suspension(portal):
    """稼働状態とログイン設定を取得し、登録済みの商品を管理者が停止できる。"""
    assert portal.get("/api/health").json() == {"status": "ok"}
    assert portal.get("/api/config").json()["demo"] is True
    asset = (
        portal.post("/api/apis", headers=headers(portal, "provider"), json=FORM)
        .raise_for_status()
        .json()
    )
    result = portal.put(
        f"/api/apis/{asset['id']}/suspension",
        params={"suspended": True},
        headers=headers(portal, "admin"),
    )
    assert result.status_code == 200
    assert result.json()["id"] == asset["id"]


def test_generated_catalog_search(portal, contract_cache):
    """公開仕様から生成した検索条件でカタログを取得し、検索結果の本文を検査できる。"""
    from hypothesis import given, settings

    identity = headers(portal, "admin")
    operation = contract_cache["portal"].schema["/api/apis"]["GET"]

    @settings(max_examples=12, deadline=None, derandomize=True)
    @given(operation.as_strategy())
    def search(case):
        response = portal.get("/api/apis", params=case.query or {}, headers=identity)
        assert response.status_code == 200

    search()
