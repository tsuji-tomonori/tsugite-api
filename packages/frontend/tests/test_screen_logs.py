import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock


def test_screen_error_context(portal_module, monkeypatch):
    """画面内の入力不備と不具合を区別し、商品と本人の識別子だけを残す。"""
    client = portal_module("client")
    client.window.location = SimpleNamespace(hash="#/edit/product-1")
    client.window.console = Mock()
    monkeypatch.setattr(client, "viewer", lambda: "person-1")
    client.report(client.InputError("private message"), "save")
    client.report(KeyError("private message"), "render")
    warning = json.loads(client.window.console.warn.call_args.args[0])
    error = json.loads(client.window.console.error.call_args.args[0])
    assert warning["level"] == "WARN" and error["level"] == "ERROR"
    assert error["actor_id"] == "person-1" and error["screen"] == "edit"
    assert error["asset_id"] == "product-1" and error["operation"] == "render"
    assert "private message" not in str(error) + str(warning)
    client.report(client.ResponseError("handled"), "save")
    assert client.window.console.error.call_count == 1


def test_request_carries_screen(portal_module, monkeypatch):
    """API呼び出しには登録済み画面の識別子だけを付加する。"""
    client = portal_module("client")
    client.window.location = SimpleNamespace(hash="#/guide/a-private-article")
    monkeypatch.setattr(client, "viewer", lambda: "person-1")
    monkeypatch.setattr(client, "store", Mock(getItem=Mock(return_value=None)))
    fetch = AsyncMock(return_value=SimpleNamespace(ok=True, json=AsyncMock(return_value={})))
    monkeypatch.setattr(client, "pyfetch", fetch)
    asyncio.run(client.api("/me"))
    assert fetch.call_args.kwargs["headers"] == {"X-Tsugite-Screen": "guide"}
    for route in ("departments", "projects"):
        client.window.location.hash = "#/" + route + "/detail/private-unit"
        assert client.screen_headers() == {"X-Tsugite-Screen": route}
    client.window.location.hash = "#/private-value"
    assert client.screen_headers() == {}
