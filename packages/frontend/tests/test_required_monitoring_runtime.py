"""監視画面に共通の操作制御と障害報告を、利用者が操作を再開できる条件で検証する。"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from test_required_people_support import Module


def test_block_repeated_monitoring_action_until_first_completes(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """監視画面が読み込み中の再操作を重複実行せず、完了後は次の要求を受け付ける。"""
    ui = portal_module("runtime.portal_ui")
    document = Mock()
    screen = document.getElementById.return_value
    monkeypatch.setattr(ui, "document", document)
    monkeypatch.setattr(ui, "render", Mock())
    next_request = AsyncMock()

    async def exercise() -> None:
        started = asyncio.Event()
        finish = asyncio.Event()

        async def reload() -> None:
            started.set()
            await finish.wait()

        running = asyncio.create_task(ui.run(reload))
        await asyncio.wait_for(started.wait(), 2)
        try:
            assert ui.ctx["busy"] and screen.inert
            await ui.run(next_request)
            next_request.assert_not_awaited()
        finally:
            finish.set()
            await running
        assert not ui.ctx["busy"] and not screen.inert
        await ui.run(next_request)
        next_request.assert_awaited_once()

    asyncio.run(exercise())


def test_failed_monitoring_query_records_action_and_releases_screen(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """集計操作が失敗すると対象操作を運用ログに渡し、画面に理由を示して入力を再開できる。"""
    ui = portal_module("runtime.portal_ui")
    document = Mock()
    monkeypatch.setattr(ui, "document", document)
    monkeypatch.setattr(ui, "render", Mock())
    session = Mock()
    session.getItem.return_value = None
    monkeypatch.setattr(ui.client, "store", session)
    report = Mock()
    monkeypatch.setattr(ui.client, "report", report)
    failure = RuntimeError("集計結果を取得できません")

    async def refresh_metrics() -> None:
        raise failure

    asyncio.run(ui.run(refresh_metrics))
    assert ui.ctx["error"] and str(failure) in ui.ctx["message"]
    assert not ui.ctx["busy"] and not document.getElementById.return_value.inert
    report.assert_called_once_with(failure, "refresh_metrics")
