# 要件「チャットで候補を確認できる」「問い合わせを送信できる」「ログインできる」の画面を検証する。
import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from test_components import render
from test_required_guide import PortalModule, visible_text


def test_chat_cites_each_product_and_guide(portal_module: PortalModule) -> None:
    """検索した商品とガイドに元情報へのリンクを付け、質問への回答と操作手順を表示する。"""
    view = portal_module("components.chat_views")
    product = {
        "id": "example-inventory",
        "name": "在庫照会",
        "summary": "倉庫の数量を返す",
        "slug": "example-inventory",
        "owner": "warehouse",
        "environments": ["sandbox", "production"],
        "published": True,
        "revision": 1,
    }
    guide = {
        "id": "apply",
        "title": "利用申請を行う",
        "steps": ["在庫照会を開く", "利用目的を入力する"],
        "result": "自分の申請で確認できる",
    }
    _, products = render(
        view.show_result, {"kind": "catalog", "answer": "在庫の候補です。", "products": [product]}
    )
    _, guides = render(
        view.show_result, {"kind": "manual", "answer": "申請の手順です。", "guides": [guide]}
    )
    links = {
        link.getAttribute("href"): visible_text(link)
        for dom in [products, guides]
        for link in dom.getElementsByTagName("a")
    }
    assert links["#/api/example-inventory"] == "在庫照会"
    assert links["#/guide/apply"]
    assert "利用申請を行う" in visible_text(guides)
    assert "在庫の候補です。" in visible_text(products)
    assert "倉庫の数量を返す" in visible_text(products)
    assert "検証" in visible_text(products) and "本番" in visible_text(products)
    guide_text = visible_text(guides)
    assert "申請の手順です。" in guide_text
    assert guide_text.index("在庫照会を開く") < guide_text.index("利用目的を入力する")


@pytest.mark.parametrize(
    ("kind", "answer"),
    [
        pytest.param(
            "empty",
            "条件に合う商品はありません。",
            id="empty",
            marks=pytest.mark.case_detail("候補がない場合は検索結果の説明だけを表示する。"),
        ),
        pytest.param(
            "outside",
            "ポータルの利用について質問してください。",
            id="outside",
            marks=pytest.mark.case_detail("扱えない質問には対応する範囲の案内を表示する。"),
        ),
        pytest.param(
            "error",
            "回答を取得できませんでした。",
            id="error",
            marks=pytest.mark.case_detail("処理の失敗時に商品や手順を表示せず案内を伝える。"),
        ),
    ],
)
def test_chat_explains_a_reply_without_sources(
    portal_module: PortalModule, kind: str, answer: str
) -> None:
    """候補を返せない回答では、その理由を伝えて商品や手順のリンクを表示しない。"""
    _, dom = render(portal_module("components.chat_views").show_result, {"kind": kind, "answer": answer})
    assert answer in visible_text(dom)
    assert not dom.getElementsByTagName("a")


def test_polling_keeps_the_receipt_until_ready(
    portal_module: PortalModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """作成中のチャットは同じ受付番号で再確認し、確定した回答を返す。"""
    messages = portal_module("apis.messages")
    job = str(uuid4())
    answer = {"kind": "manual", "answer": "申請を開きます。", "guides": []}
    fetch = AsyncMock(side_effect=[{"kind": "pending"}, answer])
    monkeypatch.setattr(messages, "get_answer", fetch)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    assert asyncio.run(messages.wait_for_result(job)) == answer
    assert [call.args for call in fetch.await_args_list] == [(job,), (job,)]


def test_chat_home_opens_an_unsent_inquiry(portal_module: PortalModule) -> None:
    """問い合わせを開くと入力欄と送信操作が現れ、送信前には受付を表示しない。"""
    chat = portal_module("components.chat_views")
    state: dict[str, Any] = {}
    _, home = render(chat.home, state, Mock())
    assert "質問" in visible_text(home) and "問い合わせ" in visible_text(home)
    assert any("問い合わせ" in visible_text(link) for link in home.getElementsByTagName("a"))
    state["chat"]["contact"] = True
    _, form = render(chat.home, state, Mock())
    assert form.getElementsByTagName("textarea")
    assert any("送信" in visible_text(button) for button in form.getElementsByTagName("button"))
    assert "受け付けました" not in visible_text(form)


@pytest.mark.parametrize(
    ("step", "purposes", "submit_action"),
    [
        pytest.param(
            "signin",
            ["username", "current-password"],
            "ログイン",
            id="signin",
            marks=pytest.mark.case_detail("ログインには利用者名と現在のパスワードを入力する。"),
        ),
        pytest.param(
            "new_password",
            ["new-password", "new-password"],
            "設定",
            id="new-password",
            marks=pytest.mark.case_detail("招待直後は新しいパスワードを確認用にも入力する。"),
        ),
        pytest.param(
            "forgot",
            ["username"],
            "送信",
            id="forgot",
            marks=pytest.mark.case_detail("再設定の開始画面では利用者名を入力して確認コードを送る。"),
        ),
        pytest.param(
            "confirm_reset",
            ["one-time-code", "new-password", "new-password"],
            "再設定",
            id="reset",
            marks=pytest.mark.case_detail("再設定には届いたコードと新しいパスワードを指定する。"),
        ),
        pytest.param(
            "setup",
            ["one-time-code"],
            "登録",
            id="totp-setup",
            marks=pytest.mark.case_detail("認証アプリの登録は確認コードを入力して確定する。"),
        ),
        pytest.param(
            "mfa",
            ["one-time-code"],
            "ログイン",
            id="totp-verification",
            marks=pytest.mark.case_detail("二要素認証ではアプリのコードを入力してログインする。"),
        ),
    ],
)
def test_login_forms_explain_the_current_step(
    portal_module: PortalModule,
    step: str,
    purposes: list[str],
    submit_action: str,
) -> None:
    """ログインの各段階で必要な入力を日本語ラベルと自動入力の用途で示す。"""
    config = {"client_id": "portal-client", "identity_endpoint": "https://identity.example.test"}
    flow = portal_module("apis.portal_auth").PortalLogin(config)
    flow.reset(step)
    form = portal_module("components.login_views").portal_form
    _, dom = render(
        form, {"config": config, "login_flow": flow, "message": ""}, Mock(), Mock(), AsyncMock()
    )
    inputs = list(dom.getElementsByTagName("input"))
    assert sorted(node.getAttribute("autocomplete") for node in inputs) == sorted(purposes)
    for node in inputs:
        label = node.parentNode
        assert label.tagName == "label" or any(
            entry.getAttribute("for") == node.getAttribute("id")
            for entry in dom.getElementsByTagName("label")
        )
        if "password" in node.getAttribute("autocomplete"):
            assert node.getAttribute("type") == "password"
    assert any(
        button.getAttribute("type") == "submit" and submit_action in visible_text(button)
        for button in dom.getElementsByTagName("button")
    )


class BrowserEvents:
    """PuePy が DOM に登録するイベントを単体テストで発火する。"""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from puepy.core import Tag

        self.events: list[tuple[Any, str, Any]] = []

        def register(_tag: Any, node: Any, event: str, handler: Any) -> None:
            self.events.append((node, event, handler))

        monkeypatch.setattr(Tag, "add_event_listener", register)

    def dispatch(self, node: Any, event: str, browser_event: Any) -> None:
        callbacks = [
            handler for element, name, handler in self.events if element is node and name == event
        ]
        assert callbacks, (node.tagName, event)
        for handler in callbacks:
            handler(browser_event)


async def finish_browser_tasks() -> None:
    pending = asyncio.all_tasks() - {asyncio.current_task()}
    if pending:
        await asyncio.gather(*pending)


def test_chat_submit_keeps_the_question_and_renders_the_received_answer(
    portal_module: PortalModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """質問を送ったら受付番号で回答を一度取得し、会話に元の質問と回答を残す。"""
    chat = portal_module("components.chat_views")
    events = BrowserEvents(monkeypatch)
    window = Mock()
    window.location.hash = "#/home"
    job = str(uuid4())
    window.crypto.randomUUID.return_value = job
    question = "棚卸しで利用できるAPIを探したい"
    field = Mock(value=question, scrollHeight=128)
    window.document.getElementById.return_value = field
    monkeypatch.setattr(chat, "window", window)
    monkeypatch.setattr(chat, "document", window.document)
    submit = AsyncMock(return_value={"job_id": job})
    answer: dict[str, Any] = {
        "kind": "catalog",
        "answer": "棚卸し用の候補を表示します。",
        "products": [],
    }
    reply = AsyncMock(return_value=answer)
    monkeypatch.setattr(chat.messages_api, "chat", submit)
    monkeypatch.setattr(chat, "wait_for_result", reply)
    state: dict[str, Any] = {}
    _, dom = render(chat.home, state, Mock())

    async def send() -> None:
        form = dom.getElementsByTagName("form")[0]
        events.dispatch(form, "submit", Mock())
        await finish_browser_tasks()

    asyncio.run(send())
    submit.assert_awaited_once_with({"job_id": job, "question": question})
    reply.assert_awaited_once_with(job)
    _, history = render(chat.home, state, Mock())
    assert question in visible_text(history)
    assert answer["answer"] in visible_text(history)
    assert not history.getElementsByTagName("input")[0].hasAttribute("disabled")


def test_only_explicit_inquiry_submission_contacts_the_operator(
    portal_module: PortalModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """問い合わせを開いただけでは送信せず、入力した利用者が送信して初めて受付となる。"""
    chat = portal_module("components.chat_views")
    events = BrowserEvents(monkeypatch)
    window = Mock()
    window.location.hash = "#/home"
    note = "提供元に受付時間を確認したい。"
    field = Mock(value=note, scrollHeight=32)
    window.document.getElementById.return_value = field
    monkeypatch.setattr(chat, "window", window)
    monkeypatch.setattr(chat, "document", window.document)
    submit = AsyncMock(return_value="inquiry-example")
    monkeypatch.setattr(chat, "post_inquiry", submit)
    state: dict[str, Any] = {}
    _, dom = render(chat.home, state, Mock())
    open_form = next(
        n for n in dom.getElementsByTagName("button") if "運営に問い合わせ" in visible_text(n)
    )
    events.dispatch(open_form, "click", Mock())
    _, opened = render(chat.home, state, Mock())
    submit.assert_not_awaited()
    textarea = opened.getElementsByTagName("textarea")[0]
    events.dispatch(textarea, "input", Mock(target=field))
    form = textarea.parentNode
    while form.tagName != "form":
        form = form.parentNode

    async def send() -> None:
        events.dispatch(form, "submit", Mock())
        await finish_browser_tasks()

    asyncio.run(send())
    submit.assert_awaited_once()
    assert submit.await_args is not None
    assert note in submit.await_args.args
    _, received = render(chat.home, state, Mock())
    assert "受け付け" in visible_text(received) or "送信しました" in visible_text(received)


@pytest.mark.parametrize(
    ("question", "available"),
    [
        pytest.param(
            " ", True, id="empty", marks=pytest.mark.case_detail("空の入力はチャット受付に送らない。")
        ),
        pytest.param(
            "在庫確認を自動化したい",
            False,
            id="unavailable",
            marks=pytest.mark.case_detail("チャットの受付障害を伝え、次の質問を入力できる状態に戻す。"),
        ),
    ],
)
def test_chat_handles_empty_input_and_service_failure(
    portal_module: PortalModule,
    monkeypatch: pytest.MonkeyPatch,
    question: str,
    available: bool,
) -> None:
    """空の質問や受付の一時障害では、会話を再開でき問い合わせを自動送信しない。"""
    chat = portal_module("components.chat_views")
    events = BrowserEvents(monkeypatch)
    window = Mock()
    window.location.hash = "#/home"
    window.crypto.randomUUID.return_value = str(uuid4())
    field = Mock(value=question, scrollHeight=42)
    window.document.getElementById.return_value = field
    monkeypatch.setattr(chat, "window", window)
    monkeypatch.setattr(chat, "document", window.document)
    accept = AsyncMock(side_effect=RuntimeError("チャット受付を一時停止しています"))
    contact = AsyncMock()
    monkeypatch.setattr(chat.messages_api, "chat", accept)
    monkeypatch.setattr(chat, "post_inquiry", contact)
    state: dict[str, Any] = {}
    _, dom = render(chat.home, state, Mock())

    async def send() -> None:
        events.dispatch(dom.getElementsByTagName("form")[0], "submit", Mock())
        await finish_browser_tasks()

    asyncio.run(send())
    _, result = render(chat.home, state, Mock())
    if available:
        accept.assert_not_awaited()
    else:
        accept.assert_awaited_once()
        assert question in visible_text(result)
        assert "チャット受付を一時停止しています" in visible_text(result)
    assert not result.getElementsByTagName("input")[0].hasAttribute("disabled")
    contact.assert_not_awaited()


def test_log_question_and_inquiry_refer_to_the_same_request(
    portal_module: PortalModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """詳細から処理時間を質問し、問い合わせを送ると同じリクエストIDを本文に含める。"""
    chat = portal_module("components.chat_views")
    events = BrowserEvents(monkeypatch)
    request_id = "trace-example"
    row = {
        "request_id": request_id,
        "key_id": None,
        "owner": "warehouse",
        "at": "2026-02-11T12:00:00Z",
        "actor": "member",
        "asset_id": "stock",
        "project": "supply",
        "operation": "/stocks",
        "method": "GET",
        "environment": "sandbox",
        "status": 200,
        "duration_ms": 427,
        "started_at": "2026-02-11T12:00:00Z",
        "responded_at": "2026-02-11T12:00:00.427Z",
        "error_code": None,
    }
    window = Mock()
    window.location.hash = "#/logs/detail"
    field = Mock(value="処理に何ミリ秒かかった？", scrollHeight=42)
    window.document.getElementById.return_value = field
    monkeypatch.setattr(chat, "window", window)
    monkeypatch.setattr(chat, "document", window.document)
    submit = AsyncMock(return_value="inquiry-example")
    monkeypatch.setattr(chat, "post_inquiry", submit)
    ctx: dict[str, Any] = {}

    def draw(inquiry: bool) -> None:
        chat.home(ctx, Mock(), log=row, path="logs/detail", inquiry_only=inquiry)

    async def send(dom: Any) -> None:
        events.dispatch(dom.getElementsByTagName("form")[0], "submit", Mock())
        await finish_browser_tasks()

    _, dom = render(draw, False)
    asyncio.run(send(dom))
    _, answered = render(draw, False)
    assert "427" in visible_text(answered)
    assert request_id in visible_text(answered)

    _, inquiry = render(draw, True)
    submit.assert_not_awaited()
    field.value = "このアクセスについて補足をお願いします。"
    events.dispatch(inquiry.getElementsByTagName("textarea")[0], "input", Mock(target=field))
    asyncio.run(send(inquiry))
    submit.assert_awaited_once()
    assert submit.await_args is not None
    body = submit.await_args.args[1]
    assert field.value in body and request_id in body
