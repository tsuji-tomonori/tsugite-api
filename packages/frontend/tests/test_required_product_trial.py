# API Docsの実行操作をブラウザーイベントから呼び、入力・送信中・結果・コピーを検証する。
import asyncio
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from puepy import t
from test_components import render


class TrialBrowser:
    """入力欄、実行ボタン、実行結果を持つAPI Docsのブラウザー境界。"""

    def __init__(self) -> None:
        self.elements: dict[str, Any] = {}
        self.events: dict[str, Callable[[Any], None]] = {}
        self.clipboard = AsyncMock()

    def element(self, identifier: str) -> Any:
        """利用者が操作できるHTML要素の状態を返す。"""
        if identifier not in self.elements:
            self.elements[identifier] = SimpleNamespace(
                value="", disabled=False, isConnected=True, hidden=False, textContent="", dataset=SimpleNamespace(),
                classList=SimpleNamespace(add=Mock(), remove=Mock()), setAttribute=Mock(), removeAttribute=Mock(),
            )
        return self.elements[identifier]

    def button(self, label: str, **attributes: Any) -> Any:
        """PuePyにボタンを描かせ、ブラウザーからのクリックを伝えられるようにする。"""
        self.events[label] = attributes["on_click"]
        return t.button(label, **attributes)

    def __getattr__(self, name: str) -> Any:
        return getattr(t, name)

    async def click(self, label: str) -> None:
        """ボタンを押し、そのクリックによって開始したすべての処理を待つ。"""
        button = self.element("submit")
        pending = asyncio.all_tasks()
        self.events[label](SimpleNamespace(target=button, currentTarget=button))
        await asyncio.gather(*(asyncio.all_tasks() - pending))


@pytest.fixture
def trial(portal_module: Callable[[str], Any], monkeypatch: pytest.MonkeyPatch) -> tuple[Any, TrialBrowser]:
    """API Docsのボタンとクリップボードを操作できるテスト用ブラウザーを準備する。"""
    import js

    browser = TrialBrowser()
    docs = portal_module("components.api_docs")
    monkeypatch.setattr(docs, "t", browser)
    monkeypatch.setattr(docs, "document", SimpleNamespace(getElementById=browser.element))
    monkeypatch.setattr(js.window, "location", SimpleNamespace(origin="https://portal.example", hash="#/api/stock"), raising=False)
    monkeypatch.setattr(js.window, "navigator", SimpleNamespace(clipboard=SimpleNamespace(writeText=browser.clipboard)), raising=False)
    browser.element("trial-key").value = "0"
    browser.element("trial-param-0").value = "商品 1"
    browser.element("trial-body").value = '{"stock": 12}'
    browser.element("trial-media").value = "application/json"
    return docs, browser


def show_trial(docs: Any, key: dict[str, Any] | None, issue: Any = None) -> None:
    """必須パスパラメータとJSON本文を持つ在庫操作を描画する。"""
    asset = {"id": "stock-id", "slug": "stock", "name": "倉庫在庫"}
    bindings = [(key, "sandbox", "finance", "finance · 検証")]
    params = [{"name": "sku", "in": "path", "required": True, "schema": {"type": "string"}}]
    body = {"required": True, "content": {"application/json": {"schema": {"type": "object"}}}}

    def view() -> None:
        docs.try_operation({}, asset, bindings, "POST", "/items/{sku}", params, body, "trial", issue_key=issue)

    render(view)


@pytest.mark.parametrize("existing", [
    pytest.param(True, id="existing", marks=pytest.mark.case_detail("既存の認証情報を使って短期トークンで実行する")),
    pytest.param(False, id="first-use", marks=pytest.mark.case_detail("初回の実行で商品専用の認証情報を発行する")),
])
def test_api_docs_runs_and_copies_curl(trial: tuple[Any, TrialBrowser], monkeypatch: pytest.MonkeyPatch, existing: bool) -> None:
    """操作を押すと選択した環境とプロジェクトへ認証付きで送り、応答・照合ID・コピー用curlを表示する。"""
    docs, browser = trial
    key = {"id": "stock-key"}
    issue = AsyncMock(return_value=key)
    auth = AsyncMock(return_value={"Authorization": "Bearer temporary-example"})
    monkeypatch.setattr(docs, "credential_headers", auth)
    result = SimpleNamespace(status=201, headers={"x-request-id": "trace-17"}, string=AsyncMock(return_value="在庫登録完了"))

    async def completed(url: str, **options: Any) -> Any:
        assert browser.element("submit").disabled
        assert "実行中" in browser.element("submit").textContent
        assert url == "https://portal.example/api/invoke/stock/sandbox/finance/items/%E5%95%86%E5%93%81%201"
        assert options["method"] == "POST" and options["body"] == '{"stock": 12}'
        assert options["headers"] == {"Content-Type": "application/json", "Authorization": "Bearer temporary-example"}
        return result

    send = AsyncMock(side_effect=completed)
    monkeypatch.setattr(docs, "fetch", send)
    show_trial(docs, key if existing else None, None if existing else issue)
    asyncio.run(browser.click("認証して実行"))
    send.assert_awaited_once()
    auth.assert_awaited_once_with(key)
    if existing:
        issue.assert_not_awaited()
    else:
        issue.assert_awaited_once_with("finance")
    output = browser.element("trial-response").textContent
    assert all(term in output for term in ("HTTP 201", "trace-17", "在庫登録完了"))
    assert not browser.element("submit").disabled and not browser.element("trial-audit").hidden
    asyncio.run(browser.click("コマンドをコピー"))
    command = browser.element("trial-curl").textContent
    assert "ACCESS_TOKEN" in command and "temporary-example" not in command
    assert '{"stock": 12}' in command
    browser.clipboard.assert_awaited_once_with(command)


@pytest.mark.parametrize(("identifier", "value", "detail"), [
    pytest.param("trial-param-0", "", "sku", id="missing-sku",
                 marks=pytest.mark.case_detail("必須のパスパラメータを空にした場合は項目名を案内する")),
    pytest.param("trial-body", "", "本文", id="missing-body",
                 marks=pytest.mark.case_detail("必須のJSON本文が空なら送信せずに本文の入力を求める")),
    pytest.param("trial-body", "{", "JSON", id="invalid-json",
                 marks=pytest.mark.case_detail("JSONとして成立しない本文では送信前に形式を案内する")),
])
def test_trial_explains_unusable_input(trial: tuple[Any, TrialBrowser], monkeypatch: pytest.MonkeyPatch,
                                      identifier: str, value: str, detail: str) -> None:
    """必須入力の不足や本文の形式不正は送信前に知らせ、修正して再実行できる。"""
    docs, browser = trial
    send = AsyncMock()
    monkeypatch.setattr(docs, "fetch", send)
    browser.element(identifier).value = value
    show_trial(docs, {"id": "stock-key"})
    asyncio.run(browser.click("認証して実行"))
    assert detail in browser.element("trial-response").textContent
    assert not browser.element("submit").disabled
    send.assert_not_awaited()
