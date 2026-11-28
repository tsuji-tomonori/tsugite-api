# ヘッダーの候補に古い応答や未確定の検索語が反映されないことを確かめる。
import asyncio
from unittest.mock import AsyncMock, Mock, call

import pytest
from test_required_guide import PortalModule


def test_superseded_suggestions(portal_module: PortalModule, monkeypatch: pytest.MonkeyPatch) -> None:
    """検索中に欄を離れると、遅れて届いた結果は閉じた候補を上書きしない。"""
    header = portal_module("components.header_search")
    view = header.Suggestions()
    field = Mock(isConnected=True)
    panel = field.form.querySelector.return_value

    async def respond(params: dict[str, object]) -> dict[str, object]:
        assert params == {"q": "夜間バッチ", "page": 1}
        view.close(field.form)
        return {"items": [{"id": "old", "name": "古い結果"}]}

    catalog = AsyncMock(side_effect=respond)
    monkeypatch.setattr(header.products, "catalog", catalog)
    monkeypatch.setattr(header.asyncio, "sleep", AsyncMock())
    asyncio.run(view.update(field, "夜間バッチ", 0))
    assert panel.hidden is True
    panel.appendChild.assert_not_called()
    asyncio.run(view.update(field, "夜間バッチ", 0))
    catalog.assert_awaited_once()


def test_suggestions_show_ranked_links_and_handle_failure(
    portal_module: PortalModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """両方の候補を上限まで表示し、API取得に失敗してもガイドの候補を開ける。"""
    header = portal_module("components.header_search")
    view = header.Suggestions()
    field = Mock(isConnected=True)
    panel = field.form.querySelector.return_value
    document = Mock()
    document.createElement.side_effect = lambda tag: Mock()
    monkeypatch.setattr(header, "document", document)
    rows = [{"id": str(n), "name": f"API{n}"} for n in range(6)]
    catalog = AsyncMock(return_value={"items": rows})
    monkeypatch.setattr(header.products, "catalog", catalog)
    monkeypatch.setattr(header.asyncio, "sleep", AsyncMock())
    asyncio.run(view.update(field, "API", 0))
    links = [entry.args[0] for entry in panel.appendChild.call_args_list]
    assert [link.href for link in links[:4]] == [f"#/api/{n}" for n in range(4)]
    assert len(links) == 8 and all(link.href.startswith("#/guide/") for link in links[4:])
    label, title = links[0].append.call_args.args
    assert (label.textContent, title) == ("API", "API0")
    panel.reset_mock()
    catalog.side_effect = header.ResponseError()
    asyncio.run(view.update(field, "夜間バッチ", 0))
    children = [entry.args[0] for entry in panel.appendChild.call_args_list]
    assert children[0].href == "#/guide/credential"
    assert children[-1].textContent == "API候補を取得できませんでした。"
    panel.reset_mock()
    catalog.side_effect = None
    catalog.return_value = {"items": []}
    asyncio.run(view.update(field, "unmatchedXYZ", 0))
    assert panel.appendChild.call_args.args[0].textContent == "候補が見つかりませんでした。"


def test_typing_and_keyboard_navigation(
    portal_module: PortalModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """短い入力と変換中は検索せず、上下キーで移動しEscapeや欄外への移動で候補を閉じる。"""
    header = portal_module("components.header_search")
    view = header.Suggestions()
    form, field, panel, link = Mock(), Mock(), Mock(), Mock()
    field.form = form
    form.querySelector.side_effect = {"input": field, ".search-suggestions": panel}.get
    event = Mock(target=field, currentTarget=form, isComposing=False)
    update = AsyncMock()
    monkeypatch.setattr(view, "update", update)

    async def type_query() -> None:
        field.value = "在"
        view.input(event)
        field.value = " 在庫 "
        event.isComposing = True
        view.input(event)
        event.isComposing = False
        view.input(event)
        await asyncio.sleep(0)

    asyncio.run(type_query())
    update.assert_awaited_once_with(field, "在庫", 3)
    event.key = "Enter"
    view.keydown(event)
    event.key = "ArrowDown"
    view.keydown(event)
    panel.hidden = False
    panel.querySelectorAll.return_value = []
    view.keydown(event)
    event.preventDefault.assert_not_called()
    panel.querySelectorAll.return_value = [link]
    event.key = "ArrowDown"
    view.keydown(event)
    link.focus.assert_called_once()
    event.target, event.key = link, "ArrowUp"
    view.keydown(event)
    field.focus.assert_called_once()
    event.key = "Escape"
    view.keydown(event)
    assert panel.hidden and view.revision == 4
    form.contains.side_effect = [True, False]
    view.blur(event)
    view.blur(event)
    assert view.revision == 5
    assert form.contains.call_args_list == [call(event.relatedTarget)] * 2
