# 公開操作のエラー経路を実際のHTTPリクエストで確認する。
from unittest.mock import Mock

from fastapi.routing import APIRoute, iter_route_contexts
from tsugite_db.session import session

from tests.support.catalog import FORM, headers, publish_asset
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


def test_missing_grants_and_catalog_entries(portal):
    """存在しない商品・申請を指定したときは、利用申請・承認・キー発行で404を返す。"""
    user = headers(portal, "consumer")
    owner = headers(portal, "provider")
    form = {"project": "finance", "environment": "sandbox", "reason": "参照先の確認"}
    assert portal.post("/api/apis/missing/requests", headers=user, json=form).status_code == 404
    key = portal.post("/api/apis", headers=owner, json=FORM).raise_for_status().json()["id"]
    for suffix in ("", "/consumer"):
        response = portal.post(
            f"/api/requests/{key}/finance/sandbox{suffix}",
            headers=owner,
            json={"action": "approve", "reason": "利用条件を確認", "revision": 1},
        )
        assert response.status_code == 404
    response = portal.post(
        "/api/keys",
        headers=user,
        json={
            "project": "finance",
            "name": "利用申請の確認",
            "kind": "personal",
            "api_ids": ["missing"],
        },
    )
    assert response.status_code == 404


def test_catalog_publication_conflicts(portal, monkeypatch):
    """更新前の版番号または登録時の接続設定が無効になった場合は409を返す。"""
    owner = headers(portal, "provider")
    asset = portal.post("/api/apis", headers=owner, json=FORM).raise_for_status().json()
    path = "/api/apis/" + asset["id"]
    response = portal.put(
        path + "/policy", params={"revision": asset["revision"] + 1}, headers=owner, json={}
    )
    assert response.status_code == 409
    monkeypatch.setattr("app.apis.catalog.publish.workspace_targets", lambda db: {})
    response = publish_asset(portal, path, owner)
    assert response.status_code == 409


def test_chat_worker_failure_responses(portal, monkeypatch):
    """チャット受付の送信制限で429を、ワーカーに接続できないときは503を返す。"""
    from uuid import uuid4

    import chat_jobs
    from botocore.exceptions import EndpointConnectionError

    monkeypatch.setenv("CHAT_WORKER", "worker")
    actor = headers(portal, "consumer")
    for error, status in [
        (chat_jobs.RateLimited(), 429),
        (EndpointConnectionError(endpoint_url="worker"), 503),
    ]:
        submit = Mock(side_effect=error)
        monkeypatch.setattr(chat_jobs, "submit", submit)
        response = portal.post(
            "/api/chat", headers=actor, json={"job_id": str(uuid4()), "question": "利用方法を確認したい"}
        )
        submit.assert_called_once()
        assert response.status_code == status
