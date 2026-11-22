import io
import json
from types import SimpleNamespace

import httpx
from app.core.config import Target
from app.integrations import upstream
from fastapi import HTTPException


def test_lambda_adapter(monkeypatch):
    """接続確認の後、呼び出し情報をLambdaへ渡して応答を返す"""
    calls = []

    def invoke(**kwargs):
        calls.append(kwargs)
        return {
            "Payload": io.BytesIO(
                json.dumps(
                    {
                        "statusCode": 200,
                        "headers": {"content-type": "application/json"},
                        "body": '{"ok":true}',
                    }
                ).encode()
            )
        }

    monkeypatch.setattr(upstream, "aws", lambda _: SimpleNamespace(invoke=invoke))
    target = Target(owner="supply", environment="sandbox", kind="lambda", address="test-function")
    upstream.probe(target)
    reply = upstream.dispatch(target, "GET", "/items", "x=1", b"", {"x-request-id": "test"})
    assert calls[0]["InvocationType"] == "DryRun"
    assert json.loads(calls[1]["Payload"])["rawPath"] == "/items"
    assert reply.status_code == 200 and json.loads(bytes(reply.body))["ok"]


def test_https_adapter(monkeypatch):
    """クエリと認証情報を保持してHTTPSの接続先に転送する"""
    sent = []

    def upstream_handler(request):
        sent.append(request)
        return httpx.Response(200, json={"ok": True})

    real_client = httpx.Client
    monkeypatch.setattr(
        upstream.httpx,
        "Client",
        lambda **opts: real_client(transport=httpx.MockTransport(upstream_handler), **opts),
    )
    secret = SimpleNamespace(get_secret_value=lambda **kwargs: {"SecretString": "unit-test-only"})
    monkeypatch.setattr(upstream, "aws", lambda _: secret)
    target = Target(
        owner="supply",
        environment="sandbox",
        kind="https",
        address="https://backend.invalid/v1",
        secret_arn="test",
    )
    upstream.probe(target)
    reply = upstream.dispatch(target, "POST", "/items", "x=1&x=2", b"data", {"x-request-id": "test"})
    assert sent[0].method == "HEAD"
    assert sent[1].url.params.get_list("x") == ["1", "2"]
    assert (
        sent[1].url.path == "/v1/items" and sent[1].headers["authorization"] == "Bearer unit-test-only"
    )
    assert reply.status_code == 200


def test_failed_probe_keeps_draft(portal, monkeypatch):
    """接続確認に失敗したAPIは下書きのまま残る"""
    import importlib

    module = importlib.import_module("app.apis.catalog.publish.router")
    from tests.support.catalog import FORM, headers

    owner = headers(portal, "provider")
    key = portal.post("/api/apis", json=FORM, headers=owner).json()["id"]

    def unavailable(target):
        raise HTTPException(502, "接続先を確認してください")

    monkeypatch.setattr(module, "probe", unavailable)
    assert portal.put(f"/api/apis/{key}/publication?published=true", headers=owner).status_code == 502
    assert not portal.get("/api/apis/" + key, headers=owner).json()["published"]
