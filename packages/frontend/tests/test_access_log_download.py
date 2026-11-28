# アクセスログのダウンロードを検証する。
from __future__ import annotations

import asyncio
from collections.abc import Callable
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


def test_failed_log_download_reports_error(
    portal_module: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    """ログ取得に失敗したときも認証ヘッダーを送り、ダウンロードを中止して理由を表示する。"""
    logs = portal_module("actions.logs")
    monkeypatch.setattr(logs.window, "Array", Mock(), raising=False)
    monkeypatch.setattr(
        portal_module("apis.client"), "store", Mock(getItem=Mock(return_value="test-token"))
    )
    monkeypatch.setattr(logs.window, "location", SimpleNamespace(hash="#/logs"), raising=False)
    logs.ctx["log_period"] = {"scope": "personal"}
    fetch = AsyncMock(return_value=SimpleNamespace(ok=False))
    monkeypatch.setattr(portal_module("apis.activity"), "fetch", fetch)
    save = Mock()
    monkeypatch.setattr(logs, "save_blob", save)

    monkeypatch.setattr(logs.window, "console", Mock(), raising=False)
    with pytest.raises(ValueError, match="ログを取得できませんでした") as error:
        asyncio.run(logs.download_logs())
    assert fetch.await_args is not None
    assert fetch.await_args.kwargs["headers"]["Authorization"] == "Bearer test-token"
    portal_module("apis.client").report(error.value, "download_logs")
    logs.window.console.error.assert_called_once()
    save.assert_not_called()
