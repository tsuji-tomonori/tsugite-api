# ポータル画面仕様のログイン導線、現在地・所属表示と狭い画面でのメニュー操作を検証する。
import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from test_components import render
from test_required_guide import PortalModule, profile, visible_text
from test_required_guide_home import BrowserEvents, finish_browser_tasks

CONFIG = {
    "demo": False,
    "identity_endpoint": "https://identity.example.test",
    "client_id": "portal",
    "domain": "",
}


def test_header_and_current_page_for_an_authenticated_reader(
    portal_module: PortalModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ログインした利用者に所属名・ガイドの現在地とログアウトを表示する。"""
    shell = portal_module("runtime.portal_shell")
    ui = portal_module("runtime.portal_ui")
    window = Mock()
    window.location.hash = "#/guide"
    window.localStorage.getItem.return_value = None
    monkeypatch.setattr(shell, "window", window)
    monkeypatch.setattr(ui, "window", window)
    monkeypatch.setitem(ui.ctx, "me", profile())
    monkeypatch.setitem(ui.ctx, "config", CONFIG)
    _, dom = render(shell.Portal.populate, Mock())
    content = visible_text(dom)
    assert "継手API" in content and "reader-project" in content and "ログアウト" in content
    assert any(
        node.getAttribute("aria-current") == "page" and "使い方ガイド" in visible_text(node)
        for node in dom.getElementsByTagName("*")
    )


def test_header_offers_signin_for_anonymous_reader(
    portal_module: PortalModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """未ログインでガイドを開くと、製品名が分かるログインフォームで案内する。"""
    shell = portal_module("runtime.portal_shell")
    ui = portal_module("runtime.portal_ui")
    window = Mock()
    window.location.hash = "#/guide"
    window.localStorage.getItem.return_value = None
    monkeypatch.setattr(ui, "window", window)
    monkeypatch.setattr(shell, "window", window)
    monkeypatch.setitem(ui.ctx, "config", CONFIG)
    monkeypatch.setitem(ui.ctx, "me", None)
    _, dom = render(shell.Portal.populate, Mock())
    assert "継手API" in visible_text(dom)
    assert any(node.getAttribute("type") == "password" for node in dom.getElementsByTagName("input"))
    assert not any("ログアウト" in visible_text(node) for node in dom.getElementsByTagName("button"))


def test_small_screen_menu_exposes_expanded_and_collapsed_states(
    portal_module: PortalModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """モバイルメニューの開閉は利用者と支援技術の両方に同じ状態を伝える。"""
    shell = portal_module("runtime.portal_shell")
    document = Mock()
    panel, button = Mock(), Mock()
    elements = {"workspace": panel, "nav-toggle": button}
    document.getElementById.side_effect = elements.get
    monkeypatch.setattr(shell, "document", document)
    for opened in (True, False):
        shell.set_navigation(opened)
        assert button.setAttribute.call_args.args == ("aria-expanded", str(opened).lower())
        assert shell.ctx["nav_open"] is opened


def test_theme_is_applied_and_remembered(
    portal_module: PortalModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ライト・ダークを選ぶと選択した表示モードを文書に反映しブラウザーに記憶する。"""
    shell = portal_module("runtime.portal_shell")
    window = Mock()
    monkeypatch.setattr(shell, "window", window)
    monkeypatch.setattr(shell, "document", window.document)
    for mode in ("light", "dark"):
        shell.theme_changed(SimpleNamespace(target=SimpleNamespace(value=mode)))
        assert window.localStorage.setItem.call_args.args[1] == mode
        assert window.document.documentElement.setAttribute.call_args.args[1] == mode


@pytest.mark.parametrize(
    ("confirmation", "accepted"),
    [
        pytest.param(
            "new-example-pass",
            True,
            id="confirmed",
            marks=pytest.mark.case_detail("初回のパスワードが一致するとログインを完了できる。"),
        ),
        pytest.param(
            "different-confirmation",
            False,
            id="different",
            marks=pytest.mark.case_detail("確認入力が一致しなければ認証を送信せず再入力を案内する。"),
        ),
    ],
)
def test_initial_password_requires_confirmation_before_login(
    portal_module: PortalModule,
    monkeypatch: pytest.MonkeyPatch,
    confirmation: str,
    accepted: bool,
) -> None:
    """初回パスワードの確認結果に応じて、ログインを確定するか入力をやり直す。"""
    views = portal_module("components.login_views")
    events = BrowserEvents(monkeypatch)
    flow = portal_module("apis.portal_auth").PortalLogin(CONFIG)
    flow.reset("new_password")
    submit = AsyncMock(return_value="example-session")
    monkeypatch.setattr(flow, "submit", submit)
    values = {"login-password": "new-example-pass", "login-repeat": confirmation}
    document = Mock()
    document.getElementById.side_effect = lambda name: (
        SimpleNamespace(value=values[name]) if name in values else None
    )
    monkeypatch.setattr(views, "document", document)
    store, refresh = Mock(), AsyncMock()
    state = {"config": CONFIG, "login_flow": flow, "message": ""}

    def action(fn: Any, *args: Any) -> Any:
        return lambda _event: asyncio.create_task(fn(*args))

    _, dom = render(views.portal_form, state, action, store, refresh)

    async def send() -> None:
        events.dispatch(dom.getElementsByTagName("form")[0], "submit", Mock())
        await finish_browser_tasks()

    if accepted:
        asyncio.run(send())
        assert submit.await_args is not None
        assert submit.await_args.kwargs["password"] == values["login-password"]
        assert any("example-session" in call.args for call in store.setItem.call_args_list)
        refresh.assert_awaited_once()
    else:
        with pytest.raises(portal_module("apis.client").InputError, match="一致"):
            asyncio.run(send())
        submit.assert_not_awaited()
        store.setItem.assert_not_called()


def test_search_from_mobile_navigation_opens_catalog_with_query(
    portal_module: PortalModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """モバイルの検索でカタログへ進むと、検索語を引き継ぎメニューを閉じる。"""
    nav = portal_module("routing.portal_navigation")
    window = Mock()
    window.matchMedia.return_value.matches = True
    monkeypatch.setattr(nav, "window", window)
    monkeypatch.setattr(nav, "load", AsyncMock())
    monkeypatch.setitem(nav.ctx, "nav_open", True)
    asyncio.run(nav.go("catalog", query="在庫確認"))
    assert window.history.pushState.call_args.args[-1] == "#/catalog"
    assert nav.ctx["query"] == "在庫確認"
    assert nav.ctx["nav_open"] is False
    nav.load.assert_awaited_once()


def test_demo_login_and_logout_restore_anonymous_home(
    portal_module: PortalModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """デモの利用者として入ると本人の所属を読み込み、ログアウトでホームの匿名状態に戻る。"""
    session = portal_module("runtime.portal_session")
    client = portal_module("apis.client")
    monkeypatch.setattr(client, "store", Mock())
    client.store.getItem.return_value = None
    monkeypatch.setattr(session, "go", AsyncMock())
    monkeypatch.setattr(session, "load", AsyncMock())
    monkeypatch.setitem(session.ctx, "config", dict(CONFIG, demo=True))
    monkeypatch.setattr(
        session.session_api, "demo", AsyncMock(return_value={"access_token": "demo-example"})
    )
    monkeypatch.setattr(session.session_api, "me", AsyncMock(return_value=profile()))
    asyncio.run(session.login("consumer"))
    session.session_api.demo.assert_awaited_once_with("consumer")
    assert session.ctx["me"]["projects"] == ["reader-project"]
    assert any("demo-example" in call.args for call in client.store.setItem.call_args_list)
    asyncio.run(session.logout())
    session.go.assert_awaited_once_with("home")
    assert not session.ctx["me"]
    assert {call.args[0] for call in client.store.setItem.call_args_list} <= {
        call.args[0] for call in client.store.removeItem.call_args_list
    }


@pytest.mark.parametrize(
    ("challenge", "step", "field", "answer"),
    [
        pytest.param(
            "SOFTWARE_TOKEN_MFA",
            "mfa",
            "SOFTWARE_TOKEN_MFA_CODE",
            "123456",
            id="totp",
            marks=pytest.mark.case_detail(
                "認証アプリの確認コードを招待先利用者の継続セッションで送る。"
            ),
        ),
        pytest.param(
            "NEW_PASSWORD_REQUIRED",
            "new_password",
            "NEW_PASSWORD",
            "example-new-pass",
            id="password",
            marks=pytest.mark.case_detail("初回パスワードを同じ利用者の継続セッションで設定する。"),
        ),
    ],
)
def test_login_challenge_continues_the_same_user_pool_session(
    portal_module: PortalModule,
    monkeypatch: pytest.MonkeyPatch,
    challenge: str,
    step: str,
    field: str,
    answer: str,
) -> None:
    """追加確認の回答は最初のログインと同じユーザープールと継続セッションに送り、成功後にログインする。"""
    auth = portal_module("apis.portal_auth")
    flow = auth.PortalLogin(CONFIG)
    request = AsyncMock(
        side_effect=[
            {"ChallengeName": challenge, "Session": "example-challenge-session"},
            {"AuthenticationResult": {"AccessToken": "example-access"}},
        ]
    )
    monkeypatch.setattr(auth, "request", request)
    assert asyncio.run(flow.submit(username="guide-reader", password="example-first-pass")) is None
    assert flow.step == step
    token = asyncio.run(flow.submit(password="example-new-pass", code="123456"))
    assert token == "example-access"
    first, confirm = request.await_args_list
    assert first.args == (CONFIG["identity_endpoint"], "InitiateAuth")
    assert first.kwargs["AuthParameters"] == {
        "USERNAME": "guide-reader",
        "PASSWORD": "example-first-pass",
    }
    assert confirm.args == (CONFIG["identity_endpoint"], "RespondToAuthChallenge")
    assert confirm.kwargs["Session"] == "example-challenge-session"
    assert confirm.kwargs["ChallengeResponses"] == {"USERNAME": "guide-reader", field: answer}


def test_incomplete_authentication_asks_for_a_new_login(
    portal_module: PortalModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """認証サービスから資格情報も次の操作も返らないときは、再ログインを日本語で案内する。"""
    auth = portal_module("apis.portal_auth")
    monkeypatch.setattr(auth, "request", AsyncMock(return_value={}))
    with pytest.raises(auth.LoginError, match="ログイン"):
        asyncio.run(
            auth.PortalLogin(CONFIG).submit(username="guide-reader", password="example-password")
        )


@pytest.mark.parametrize(
    ("page", "heading"),
    [
        pytest.param(
            "guide/credential",
            "認証情報",
            id="credential",
            marks=pytest.mark.case_detail("共有されたガイドURLから認証情報の手順を直接開ける。"),
        ),
        pytest.param(
            "guide/nonexistent-article",
            "ガイド",
            id="unknown-guide",
            marks=pytest.mark.case_detail("見つからないガイドでは一覧へ戻る案内を表示する。"),
        ),
    ],
)
def test_guide_article_can_be_opened_from_a_bookmark(
    portal_module: PortalModule,
    monkeypatch: pytest.MonkeyPatch,
    page: str,
    heading: str,
) -> None:
    """ガイド記事のブックマークは対象の内容を表示し、元の一覧に戻れる。"""
    import js

    monkeypatch.setattr(js.window, "location", SimpleNamespace(hash="#/" + page), raising=False)
    article = portal_module("pages.guide_article")
    ui = portal_module("runtime.portal_ui")
    monkeypatch.setitem(ui.ctx, "me", profile())
    assert heading in article.article_title()
    _, dom = render(article.article)
    assert any(link.getAttribute("href") == "#/guide" for link in dom.getElementsByTagName("a"))
    assert ("見つかりません" in visible_text(dom)) == page.endswith("nonexistent-article")


@pytest.mark.parametrize(
    ("user", "role"),
    [
        pytest.param(
            profile(),
            "利用者",
            id="consumer-role",
            marks=pytest.mark.case_detail("一般利用者に利用者の役割名を表示する。"),
        ),
        pytest.param(
            profile(owner=True),
            "提供者",
            id="owner-role",
            marks=pytest.mark.case_detail("提供プロジェクトを担当する人には提供者の役割名を表示する。"),
        ),
        pytest.param(
            profile(auditor=True),
            "監査担当",
            id="audit-role",
            marks=pytest.mark.case_detail("全体監査権限を持つ人には監査担当の役割名を表示する。"),
        ),
        pytest.param(
            profile(admin=True),
            "管理者",
            id="admin-role",
            marks=pytest.mark.case_detail("全体管理権限を持つ人には管理者の役割名を表示する。"),
        ),
    ],
)
def test_header_identifies_the_current_role(
    portal_module: PortalModule, monkeypatch: pytest.MonkeyPatch, user: dict[str, Any], role: str
) -> None:
    """現在の利用者区分を日本語で識別できる。"""
    ui = portal_module("runtime.portal_ui")
    monkeypatch.setitem(ui.ctx, "me", user)
    assert ui.role_title() == role


def test_mobile_breakpoint_closes_navigation_and_desktop_reveals_it(
    portal_module: PortalModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """画面を狭めるとメニューを折り畳み、十分に広くしたときはメニューを表示する。"""
    shell = portal_module("runtime.portal_shell")
    monkeypatch.setattr(shell, "document", Mock())
    shell.adapt_navigation(SimpleNamespace(matches=True))
    assert shell.ctx["nav_open"] is False
    shell.adapt_navigation(SimpleNamespace(matches=False))
    assert shell.ctx["nav_open"] is True


def test_demo_login_lets_the_reader_choose_a_role_or_invited_user(
    portal_module: PortalModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ローカルのデモでは業務の役割を選ぶか追加済み利用者のメールアドレスでログインできる。"""
    login = portal_module("components.login")
    ui = portal_module("runtime.portal_ui")
    monkeypatch.setitem(ui.ctx, "config", dict(CONFIG, demo=True))
    _, dom = render(login.login_panel)
    buttons = [visible_text(button) for button in dom.getElementsByTagName("button")]
    for role in ("利用", "提供", "監査", "管理"):
        assert any(role in label for label in buttons)
    assert any(
        "メールアドレス" in visible_text(label) and label.getElementsByTagName("input")
        for label in dom.getElementsByTagName("label")
    )
