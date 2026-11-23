import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


def test_console_reads_only_approved_spec(portal_module, monkeypatch):
    """承認済みの申請だけを候補にし、失効した商品の直接指定では仕様を取得しない。"""
    page = portal_module("portal_pages.console")
    rights = [
        {"asset_id": "ok", "status": "approved"},
        {"asset_id": "held", "status": "pending"},
        {"asset_id": "old", "status": "revoked"},
    ]
    api = AsyncMock(side_effect=[rights, [], {"id": "ok"}])
    monkeypatch.setattr(page.client, "api", api)
    asyncio.run(page.load_console("console/old"))
    assert api.await_count == 2
    assert page.ctx["console_rights"] == rights[:1]
    assert page.ctx["console_asset"] is None
    asyncio.run(page.open_asset("ok"))
    api.assert_awaited_with("/apis/ok")
    assert page.ctx["console_asset"] == {"id": "ok"}


def test_only_allowed_operations_and_environments(portal_module):
    """本人に許可された操作と承認環境を選べ、操作制限のある委任認証は候補から外れる。"""
    page = portal_module("portal_pages.console")
    spec = {"paths": {"/item": {"get": {"summary": "読む"}, "post": {}, "trace": {}}}}
    asset = {
        "id": "stock",
        "spec": spec,
        "allowed_operations": ["GET /item"],
        "environments": ["sandbox"],
    }
    grant = {"asset_id": "stock", "environment": "sandbox", "project": "finance", "status": "approved"}
    key = {
        "id": "app",
        "name": "委任",
        "kind": "personal",
        "mode": "app",
        "creator": "alice",
        "project": "finance",
        "operations": {"stock": ["POST /item"]},
    }
    page.ctx.update(
        me={"subject": "alice"},
        console_rights=[grant, dict(grant, environment="production")],
        console_keys=[key],
    )
    assert list(page.operations(asset)) == ["GET /item"]
    options = page.bindings(asset, "GET /item")
    assert [row[:3] for row in options] == [(None, "sandbox", "finance")]
    assert page.bindings(asset, "POST /item")[-1][0] == key


def test_identity_and_delegated_token(portal_module, monkeypatch):
    """本人の認証ではログイントークンを使い、委任認証では本人確認後に短期トークンを取得する。"""
    docs = portal_module("api_docs")
    monkeypatch.setattr(docs.client, "screen_headers", lambda: {"X-Tsugite-Screen": "console"})
    monkeypatch.setattr(docs.client, "store", SimpleNamespace(getItem=lambda _: "session"))
    response = SimpleNamespace(ok=True, json=AsyncMock(return_value={"access_token": "delegated"}))
    exchange = AsyncMock(return_value=response)
    monkeypatch.setattr(docs, "pyfetch", exchange)
    headers = asyncio.run(docs.credential_headers(None))
    assert headers == {"Authorization": "Bearer session", "X-Tsugite-Screen": "console"}
    exchange.assert_not_awaited()
    token = asyncio.run(docs.credential_headers({"mode": "app", "id": "mine"}))
    exchange.assert_awaited_once_with("/api/credentials/mine/token", method="POST", headers=headers)
    assert token == {"Authorization": "Bearer delegated", "X-Tsugite-Screen": "console"}


def test_manual_request_uses_only_entered_headers(portal_module, monkeypatch):
    """URL直接指定では入力したヘッダーと本文だけを使い、Cookieとリダイレクトを無効にする。"""
    manual = portal_module("manual_request")
    fields = {
        "url": "https://example.test/orders?a=1",
        "method": "POST",
        "body": "  payload  ",
        "headers": "X-Client: local",
    }
    document = SimpleNamespace(getElementById=lambda key: SimpleNamespace(value=fields[key[7:]]))
    monkeypatch.setattr(manual, "document", document)
    fetch = AsyncMock(return_value=SimpleNamespace(status=409, string=AsyncMock(return_value="重複")))
    monkeypatch.setattr(manual, "pyfetch", fetch)
    button, output = Mock(disabled=True), Mock()
    asyncio.run(manual.send(button, output))
    fetch.assert_awaited_once_with(
        fields["url"],
        method="POST",
        headers={"x-client": "local"},
        credentials="omit",
        redirect="error",
        referrerPolicy="no-referrer",
        cache="no-store",
        body="  payload  ",
    )
    assert output.textContent == "HTTP 409\n重複"
    assert button.disabled is False


def test_invalid_manual_requests_are_rejected(portal_module):
    """送信先やヘッダーの形式が不正な場合やGETに本文がある場合は送信前にエラーになる。"""
    manual = portal_module("manual_request")
    for url in ("//example.test", "file:///local", "https://user:pass@example.test"):
        with pytest.raises(manual.client.InputError, match="URL"):
            manual.request_options(url, "POST", "", "")
    with pytest.raises(manual.client.InputError, match="ヘッダー"):
        manual.request_options("https://example.test", "GET", "missing delimiter", "")
    with pytest.raises(manual.client.InputError, match="本文"):
        manual.request_options("https://example.test", "GET", "", "body")
