# ログ取得に失敗したときも認証ヘッダーを送り、ダウンロードを中止して理由を表示する。
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


def test_failed_log_download_reports_error(portal_module, monkeypatch):
    """ログ取得に失敗したときも認証ヘッダーを送り、ダウンロードを中止して理由を表示する。"""
    logs = portal_module("portal_pages.logs")
    monkeypatch.setattr(logs.window, "Array", Mock(), raising=False)
    monkeypatch.setattr(logs.client, "store", Mock(getItem=Mock(return_value="test-token")))
    monkeypatch.setattr(logs.window, "location", SimpleNamespace(hash="#/logs"), raising=False)
    logs.ctx["log_period"] = {"scope": "personal"}
    fetch = AsyncMock(return_value=SimpleNamespace(ok=False))
    monkeypatch.setattr(logs, "pyfetch", fetch)
    save = Mock()
    monkeypatch.setattr(logs, "save_blob", save)

    monkeypatch.setattr(logs.window, "console", Mock(), raising=False)
    with pytest.raises(ValueError, match="ログを取得できませんでした") as error:
        asyncio.run(logs.download_logs())
    assert fetch.await_args.kwargs["headers"]["Authorization"] == "Bearer test-token"
    logs.client.report(error.value, "download_logs")
    logs.window.console.error.assert_called_once()
    save.assert_not_called()
