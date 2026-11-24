# 要件「ポータルにログインできる」「通知を配信できる」で、起動と個人別の未読表示を検証する。
import asyncio
import sys
from collections.abc import Coroutine
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from test_required_guide import PortalModule, profile
from test_required_guide_navigation import CONFIG


@pytest.fixture
def browser_app(portal_module: PortalModule, monkeypatch: pytest.MonkeyPatch) -> Any:
    import js

    ui = portal_module("runtime.portal_ui")
    monkeypatch.setattr(ui.app, "mount", Mock())
    monkeypatch.setattr(js.window, "matchMedia", Mock(), raising=False)
    wrappers = SimpleNamespace(add_event_listener=Mock())
    monkeypatch.setitem(sys.modules, "pyodide.ffi.wrappers", wrappers)

    def skip_background_start(coro: Coroutine[Any, Any, Any]) -> None:
        coro.close()

    with monkeypatch.context() as temporary:
        temporary.setattr(asyncio, "ensure_future", skip_background_start)
        app = portal_module("app")
    window = Mock()
    window.localStorage.getItem.return_value = None
    monkeypatch.setattr(app, "window", window)
    monkeypatch.setattr(app, "document", window.document)
    return app


@pytest.mark.parametrize(
    "stored_session",
    [
        pytest.param(
            None,
            id="signed-out",
            marks=pytest.mark.case_detail("未ログインなら本人の情報を要求せずログイン設定を取得する。"),
        ),
        pytest.param(
            "example-session",
            id="signed-in",
            marks=pytest.mark.case_detail("既存のログインがあれば本人の情報を更新する。"),
        ),
    ],
)
def test_start_loads_portal_configuration_and_restores_a_session(
    browser_app: Any,
    monkeypatch: pytest.MonkeyPatch,
    stored_session: str | None,
) -> None:
    """起動時に配備されたAPIの入口と設定を読み込み、保存済みのログインがある場合に本人を取得する。"""
    entry = Mock(json=AsyncMock(return_value={"api_prefix": "/api"}))
    monkeypatch.setattr(browser_app, "fetch", AsyncMock(return_value=entry))
    monkeypatch.setattr(browser_app.session_api, "config", AsyncMock(return_value=CONFIG))
    monkeypatch.setattr(browser_app.client, "callback", AsyncMock())
    store = Mock()
    store.getItem.return_value = stored_session
    monkeypatch.setattr(browser_app.client, "store", store)
    monkeypatch.setattr(browser_app, "refresh_session", AsyncMock())
    asyncio.run(browser_app.start())
    assert browser_app.ctx["config"] == CONFIG
    assert browser_app.ctx["busy"] is False
    browser_app.fetch.assert_awaited_once_with("/entry.json")
    browser_app.session_api.config.assert_awaited_once()
    assert browser_app.refresh_session.await_count == int(stored_session is not None)


def test_notification_poll_updates_signed_in_readers_badge(
    browser_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """未読件数の更新でログイン中の利用者のベルに最新の件数を反映する。"""
    monkeypatch.setitem(browser_app.ctx, "me", profile())
    monkeypatch.setitem(browser_app.ctx, "badge", 0)
    monkeypatch.setitem(browser_app.ctx, "busy", False)
    browser_app.document.hidden = False
    browser_app.document.visibilityState = "visible"
    monkeypatch.setattr(browser_app.messages_api, "unread", AsyncMock(return_value={"unread": 3}))
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(side_effect=[None, asyncio.CancelledError()]))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(browser_app.poll_badge())
    assert browser_app.ctx["badge"] == 3, (
        browser_app.messages_api.unread.await_count,
        browser_app.document.mock_calls,
    )
