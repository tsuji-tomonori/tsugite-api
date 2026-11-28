"""ログ一件の表示とページ移動を検証する。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock

import pytest
from puepy import Page

ROW = {
    "at": "2026-11-23T09:57:09.010+00:00",
    "started_at": None,
    "responded_at": None,
    "duration_ms": 357,
    "status": 429,
    "error_code": "rate_limited",
    "request_id": "id+/=",
    "method": "GET",
    "operation": "/items",
    "actor": "consumer",
    "owner": "supply",
    "project": "finance",
    "asset_id": "inventory",
    "environment": "sandbox",
    "key_id": None,
}


def test_detail_timestamps_and_answers(portal_module: Callable[[str], ModuleType]) -> None:
    """過去分の推定時刻と実測時刻を区別し、質問には選んだ記録の結果と識別子で答える。"""
    display = portal_module("content.access_log_display")
    fields = dict(display.detail_fields(ROW))
    assert fields["呼び出し開始"] == "2026-11-23 09:57:08.653 UTC（推定）"
    assert fields["応答"].endswith("09.010 UTC（記録時刻から推定）")
    assert fields["処理時間"] == "357 ms" and fields["キーID"] == "なし"
    assert "rate_limited" in display.answer_log_question(ROW, "エラーの原因は？")
    assert "357 ms" in display.answer_log_question(ROW, "何秒？")
    assert "consumer" in display.answer_log_question(ROW, "誰が呼んだ？")
    assert display.answer_log_question(ROW, "明日の天気を教えて") is None
    assert "処理時間" in display.answer_log_question(ROW, "概要を教えて")
    measured = {**ROW, "status": 200, "started_at": ROW["at"], "responded_at": ROW["at"]}
    assert "推定" not in str(display.timing(measured))
    assert "エラーコード" not in dict(display.detail_fields(measured))


def test_detail_link_preserves_scope_and_id(
    portal_module: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    """共有用URLから記号を含む元のIDと閲覧範囲を復元し、1件だけを読み込む。"""
    logs = portal_module("actions.logs")
    api = AsyncMock(return_value=ROW)
    monkeypatch.setattr(portal_module("apis.client"), "api", api)
    page = logs.detail_path("id+/=", "team", "chat", audit=True)
    monkeypatch.setattr(logs, "route", lambda: page)
    asyncio.run(logs.load_detail(page))
    api.assert_awaited_once_with("/access-logs/detail?request_id=id%2B%2F%3D&unit=team&scope=audit")
    assert logs.ctx["log_detail"] == (page, ROW, "team", "chat")


def test_log_page_shows_only_requested_rows(
    portal_module: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    """次ページ確認用の21件目を表に出さず、最終ページで次への案内を消す。"""
    from unittest.mock import patch
    from xml.dom.minidom import Document

    from puepy.core import Tag

    logs = portal_module("components.logs")
    monkeypatch.setattr(logs, "filters_view", lambda _, **kwargs: None)
    logs.ctx["log_rows"] = [{**ROW, "request_id": f"id-{n}"} for n in range(21)]

    class ListPage(Page):
        def populate(self) -> None:
            logs.logs_view()

    def table_page() -> Any:
        page = ListPage()
        with page:
            page.generate_children()
        with patch.object(Tag, "document", Document()):
            return page.render()

    dom = table_page()
    assert len(dom.getElementsByTagName("tr")) == 21
    assert "id-20" not in dom.toxml() and "次へ" in dom.toxml()
    logs.ctx.update(log_offset=20, log_rows=[{**ROW, "request_id": "id-20"}])
    xml = table_page().toxml()
    assert "21～21件" in xml and "次へ" not in xml and "前へ" in xml


def test_paging_back_keeps_the_time_window(
    portal_module: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    """前のページに戻る間に新しい呼び出しがあっても、検索期間を固定して同じ行を表示する。"""
    from unittest.mock import Mock
    from urllib.parse import parse_qs, urlsplit

    logs = portal_module("actions.logs")
    monkeypatch.setattr(logs, "load_dimensions", AsyncMock())
    monkeypatch.setattr(portal_module("apis.client"), "api", AsyncMock(return_value=[]))
    periods = Mock(side_effect=[{"end": "first"}, {"end": "refreshed"}])
    monkeypatch.setattr(logs, "time_params", periods)
    asyncio.run(logs.load_logs("logs"))
    asyncio.run(logs.log_page(20))
    asyncio.run(logs.log_page(0))
    asyncio.run(logs.load_logs("logs"))
    queries = [
        parse_qs(urlsplit(call.args[0]).query)
        for call in portal_module("apis.client").api.await_args_list
    ]
    assert [(q["offset"][0], q["end"][0]) for q in queries] == [
        ("0", "first"),
        ("20", "first"),
        ("0", "first"),
        ("0", "refreshed"),
    ]
