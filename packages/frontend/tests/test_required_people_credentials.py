"""発行条件の選択と正規の発行操作を、認証情報の利用手順と公開API仕様に照らして検証する。"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from test_components import render
from test_required_people_support import (
    Buttons,
    Module,
    Record,
    content,
    member,
    person,
    row_with,
    unit,
    workspace,
)


def options(*, manager: bool, limit: int) -> Record:
    return {
        "assets": [
            {
                "id": "stock",
                "name": "在庫照会",
                "operations": ["GET /items", "POST /orders"],
                "max_minutes": limit,
            }
        ],
        "members": [person("u-1", "受発注担当", "stock@example.test")],
        "limits": [{"name": "配送本部", "minutes": limit}],
        "max_minutes": limit,
        "may_manage": manager,
    }


def control(dom: Any, element_id: str) -> Any:
    return next(el for el in dom.getElementsByTagName("*") if el.getAttribute("id") == element_id)


@pytest.mark.parametrize(
    ("manager", "limit"),
    [
        pytest.param(
            True,
            60,
            id="leader",
            marks=pytest.mark.case_detail("リーダーはシステム認証を選べ、標準値で60分・45分を表示する"),
        ),
        pytest.param(
            False,
            20,
            id="member",
            marks=pytest.mark.case_detail("メンバーは本人用の方式を選び、部署の20分上限が適用される"),
        ),
    ],
)
def test_credential_modes_and_validity(portal_module: Module, manager: bool, limit: int) -> None:
    """対象プロジェクトの権限と有効期間上限に合った方式と発行条件を選べる。"""
    views = portal_module("components.credential_views")
    controls = portal_module("components.controls")
    state = {"me": {"subject": "u-1", "projects": ["finance"], "personal_project": "person-1"}}
    dom = render(
        views.render_form,
        state,
        "finance",
        options(manager=manager, limit=limit),
        controls.field,
        controls.btn,
        AsyncMock(),
    )[1]
    modes = {
        opt.getAttribute("value") for opt in control(dom, "cred-mode").getElementsByTagName("option")
    }
    assert {"bearer", "app"} <= modes
    assert ("system" in modes) == manager
    duration = control(dom, "cred-ttl")
    assert int(duration.getAttribute("max")) == limit
    assert int(duration.getAttribute("value")) == limit
    refresh = int(control(dom, "cred-refresh").getAttribute("value"))
    assert 1 <= refresh <= limit
    if limit == 60:
        assert refresh == 45
    for label in ("在庫照会", "GET /items", "POST /orders", "受発注担当", "配送本部"):
        assert label in content(dom)


def test_legacy_key_scope_and_project(portal_module: Module) -> None:
    """従来キーの発行では対象プロジェクト、共有・本人限定と承認済みのAPIを選べる。"""
    view = portal_module("components.keys")
    dom = render(
        view.key_form, [("stock", "在庫管理")], [{"id": "inv", "name": "棚卸照会"}], AsyncMock()
    )[1]
    text = content(dom)
    for label in ("在庫管理", "共有", "本人", "棚卸照会"):
        assert label in text
    assert any(o.getAttribute("value") == "stock" for o in dom.getElementsByTagName("option"))


def test_issue_app_with_selected_operation(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """アプリ認証を発行すると指定した利用者・API操作・更新時刻を発行サービスに渡す。"""
    views = portal_module("components.credential_views")
    access = portal_module("apis.access")
    controls = portal_module("components.controls")
    state = {"me": {"subject": "u-1", "projects": ["finance"], "personal_project": "person-1"}}
    submitted = AsyncMock(
        return_value={"id": "issued", "client_id": "client", "client_secret": "example"}
    )
    monkeypatch.setattr(access, "issue", submitted)
    inputs = {
        "cred-name": "棚卸アプリ",
        "credential-project": "finance",
        "cred-mode": "app",
        "cred-kind": "shared",
        "cred-scope": "selected",
        "cred-actions-0": "selected",
        "cred-user-scope": "selected",
        "cred-ttl": "18",
        "cred-refresh": "12",
    }
    monkeypatch.setattr(views, "val", inputs.__getitem__)
    selected = {"cred-api-0", "cred-op-0-0", "cred-user-0"}
    monkeypatch.setattr(views, "checked", selected.__contains__)
    buttons = Buttons(controls)

    reload = AsyncMock()
    render(
        views.render_form,
        state,
        "finance",
        options(manager=True, limit=20),
        controls.field,
        buttons,
        reload,
    )
    buttons.click("認証情報を発行")
    submitted.assert_awaited_once()
    assert submitted.await_args is not None
    body = submitted.await_args.args[0]
    for key, value in {
        "project": "finance",
        "mode": "app",
        "name": "棚卸アプリ",
        "api_ids": ["stock"],
        "operations": {"stock": ["GET /items"]},
        "users": ["u-1"],
        "ttl_minutes": 18,
        "refresh_minutes": 12,
    }.items():
        assert body[key] == value


def issued(mode: str, *, revoked: bool = False) -> Record:
    """一覧の発行済み認証情報を公開APIと同じ項目で用意する。"""
    return {
        "id": f"key-{mode}",
        "name": f"棚卸-{mode}",
        "mode": mode,
        "project": "stock",
        "kind": "shared" if mode == "system" else "personal",
        "creator": "operator",
        "api_ids": ["inventory"],
        "revoked": revoked,
        "ttl_minutes": 30,
        "refresh_minutes": 20,
        "operations": {"inventory": ["GET /stock"]},
        "users": [],
        "can_portal_exchange": True,
    }


def test_key_directory_explains_each_method(portal_module: Module) -> None:
    """発行済みの方式に応じて利用範囲・有効期限・呼び出し方と失効状態を確認できる。"""

    keys = portal_module("components.keys")
    ui = portal_module("runtime.portal_ui")
    ui.ctx.update(
        me=member(admin=True),
        workspace=workspace([unit("stock", "在庫管理", "project")], admin=True),
        keys=[issued(mode) for mode in ("app", "bearer", "system", "legacy")]
        + [dict(issued("app", revoked=True), name="失効したアプリ", id="old-app")],
        key_assets=[{"id": "inventory", "name": "棚卸照会"}],
    )
    dom = render(keys.keys_view)[1]
    for mode in ("bearer", "app", "system"):
        row = content(row_with(dom, f"棚卸-{mode}"))
        for label in ("30分", "20分", "GET /stock", "在庫管理"):
            assert label in row
        if mode in ("app", "system"):
            assert "/api/auth/token" in row and "client_secret" in row
    assert "X-API-Key" in content(row_with(dom, "棚卸-legacy"))
    old = row_with(dom, "失効したアプリ")
    assert "失効" in content(old)
    assert not old.getElementsByTagName("button")


@pytest.mark.parametrize(
    ("mode", "button", "operation", "result"),
    [
        pytest.param(
            "app",
            "シークレットを更新",
            "rotate",
            {"client_id": "key-app", "client_secret": "replacement-example"},
            id="rotate",
            marks=pytest.mark.case_detail("アプリのシークレットを更新して発行結果を確認する"),
        ),
        pytest.param(
            "bearer",
            "アクセストークンを取得・更新",
            "token",
            {
                "access_token": "sample-token",
                "expires_in": 1800,
                "refresh_after": 1200,
                "token_type": "Bearer",
            },
            id="refresh",
            marks=pytest.mark.case_detail("短期Bearerを更新し新しいアクセストークンを確認する"),
        ),
    ],
)
def test_manage_issued_credential(
    portal_module: Module,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    button: str,
    operation: str,
    result: Record,
) -> None:
    """対象行の更新操作は選択した認証情報を更新し、新しく発行された資格を画面に表示する。"""

    views = portal_module("components.credential_views")
    api = portal_module("apis.access")
    controls = portal_module("components.controls")
    ui = portal_module("runtime.portal_ui")
    js = portal_module("js")
    ui.ctx.update(
        me=member(admin=True),
        keys=[issued(mode)],
        key_assets=[{"id": "inventory", "name": "在庫照会"}],
        workspace=workspace([unit("stock", "在庫管理", "project")], admin=True),
    )
    perform = AsyncMock(return_value=result)
    monkeypatch.setattr(api, operation, perform)
    monkeypatch.setattr(js.window, "confirm", lambda _: True, raising=False)
    buttons = Buttons(controls)

    refresh = AsyncMock()
    projects = [("stock", "在庫管理")]
    render(views.credentials_view, ui.ctx, controls.field, buttons, refresh, projects)
    buttons.click(button)
    perform.assert_awaited_once_with(f"key-{mode}")
    page = portal_module("components.keys")
    monkeypatch.setattr(page, "btn", buttons)
    dom = render(page.keys_view)[1]
    new_value = result.get("access_token") or result["client_secret"]
    assert new_value in dom.toxml()

    copy = AsyncMock()
    monkeypatch.setattr(
        js.window, "navigator", SimpleNamespace(clipboard=SimpleNamespace(writeText=copy)), raising=False
    )
    buttons.click("クライアントシークレットをコピー" if mode == "app" else "アクセストークンをコピー")
    copy.assert_awaited_once_with(new_value)
    buttons.click("秘密の表示を閉じる")
    assert new_value not in render(page.keys_view)[1].toxml()


def test_refresh_project_conditions(portal_module: Module, monkeypatch: pytest.MonkeyPatch) -> None:
    """発行先を選んで条件を取得すると、選択したプロジェクトのAPIと操作が発行画面に現れる。"""

    views = portal_module("components.credential_views")
    access = portal_module("apis.access")
    controls = portal_module("components.controls")
    ui = portal_module("runtime.portal_ui")
    ui.ctx.update(me=member(), keys=[], workspace=workspace([unit("stock", "在庫管理", "project")]))
    request = AsyncMock(return_value=options(manager=False, limit=20))
    monkeypatch.setattr(access, "options", request)
    monkeypatch.setattr(views, "val", {"credential-project": "stock"}.__getitem__)
    buttons = Buttons(controls)

    projects = [("stock", "在庫管理")]
    reload = AsyncMock()
    render(views.credentials_view, ui.ctx, controls.field, buttons, reload, projects)
    buttons.click("発行条件を確認")
    request.assert_awaited_once_with("stock")
    dom = render(views.credentials_view, ui.ctx, controls.field, buttons, reload, projects)[1]
    for label in ("在庫照会", "GET /items", "配送本部", "20分"):
        assert label in content(dom)


@pytest.mark.parametrize(
    ("mode", "kind", "scope", "selected", "expected_apis"),
    [
        pytest.param(
            "bearer",
            "personal",
            "all",
            set(),
            [],
            id="personal-all",
            marks=pytest.mark.case_detail("短期Bearerは承認済みの全APIを利用範囲にできる"),
        ),
        pytest.param(
            "system",
            "shared",
            "selected",
            {"cred-api-0"},
            ["stock"],
            id="system-api",
            marks=pytest.mark.case_detail("無人実行用には特定APIの全操作を選択できる"),
        ),
    ],
)
def test_issue_whole_api_access(
    portal_module: Module,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    kind: str,
    scope: str,
    selected: set[str],
    expected_apis: list[str],
) -> None:
    """個別の操作を絞らない場合でも方式・プロジェクト・指定APIとトークンの期限を保存する。"""

    view = portal_module("components.credential_views")
    api = portal_module("apis.access")
    controls = portal_module("components.controls")
    inputs = {
        "credential-project": "stock",
        "cred-name": "集計",
        "cred-mode": mode,
        "cred-kind": kind,
        "cred-scope": scope,
        "cred-actions-0": "all",
        "cred-user-scope": "all",
        "cred-ttl": "30",
        "cred-refresh": "19",
    }
    monkeypatch.setattr(view, "val", inputs.__getitem__)
    monkeypatch.setattr(view, "checked", selected.__contains__)
    received = AsyncMock(
        return_value={
            "id": "k-new",
            "client_id": "k-new",
            "client_secret": "example",
            "access_token": "test-value",
            "expires_in": 1800,
            "refresh_after": 1140,
        }
    )
    monkeypatch.setattr(api, "issue", received)
    buttons = Buttons(controls)

    render(
        view.render_form,
        {"me": member(admin=True)},
        "stock",
        options(manager=True, limit=30),
        controls.field,
        buttons,
        AsyncMock(),
    )
    buttons.click("認証情報を発行")
    assert received.await_args is not None
    data = received.await_args.args[0]
    assert (data["project"], data["name"], data["mode"], data["api_ids"]) == (
        "stock",
        "集計",
        mode,
        expected_apis,
    )
    assert (data["ttl_minutes"], data["refresh_minutes"]) == (30, 19)


@pytest.mark.parametrize(
    ("kind", "scope", "assets"),
    [
        pytest.param(
            "shared",
            "all",
            [],
            id="shared-all",
            marks=pytest.mark.case_detail("共有キーは承認済みのAPI全体に発行できる"),
        ),
        pytest.param(
            "personal",
            "selected",
            ["inventory"],
            id="personal-specific",
            marks=pytest.mark.case_detail("本人限定キーは指定したAPIだけに発行できる"),
        ),
    ],
)
def test_issue_legacy_key(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch, kind: str, scope: str, assets: list[str]
) -> None:
    """従来キーの発行フォームが選択した範囲で発行し、受け取ったキーを利用者に提示する。"""

    page = portal_module("components.keys")
    api = portal_module("apis.access")
    ui = portal_module("runtime.portal_ui")
    js = portal_module("js")
    inputs = {"key-name": "棚卸担当", "key-project": "stock", "key-scope": scope, "key-kind": kind}
    ui.ctx.update(
        me=member(),
        workspace=workspace([unit("stock", "在庫移行", "project")]),
        keys=[],
        key_assets=[{"id": "inventory", "name": "在庫照会"}, {"id": "delivery", "name": "配送照会"}],
    )
    attrs = {
        "getElementById": lambda key: SimpleNamespace(
            checked=key == "key-asset-inventory", value=inputs.get(key, "")
        )
    }
    monkeypatch.setattr(page, "value", inputs.__getitem__)
    monkeypatch.setattr(js, "document", SimpleNamespace(**attrs), raising=False)
    monkeypatch.setattr(page, "document", js.document, raising=False)
    create = AsyncMock(return_value={"secret": "tsu_example_value", "id": "k-issued"})
    monkeypatch.setattr(api, "create_key", create)
    monkeypatch.setattr(page, "load", AsyncMock())
    controls = portal_module("components.controls")
    buttons = Buttons(controls)

    monkeypatch.setattr(page, "btn", buttons)
    render(page.keys_view)
    buttons.click("キーを発行")
    assert create.await_args is not None
    assert create.await_args.args[0] == {
        "name": "棚卸担当",
        "project": "stock",
        "kind": kind,
        "api_ids": assets,
    }
    issued_page = render(page.keys_view)[1]
    assert "tsu_example_value" in issued_page.toxml()
    copy = AsyncMock()
    monkeypatch.setattr(
        js.window, "navigator", SimpleNamespace(clipboard=SimpleNamespace(writeText=copy)), raising=False
    )
    buttons.click("キーをコピー")
    copy.assert_awaited_once_with("tsu_example_value")
    buttons.click("表示を閉じる")
    assert "tsu_example_value" not in render(page.keys_view)[1].toxml()


@pytest.mark.parametrize(
    ("mode", "kind", "scope", "visible"),
    [
        pytest.param(
            "app",
            "shared",
            "selected",
            True,
            id="project-app",
            marks=pytest.mark.case_detail("プロジェクトのアプリは対象API・操作・利用者を指定できる"),
        ),
        pytest.param(
            "bearer",
            "personal",
            "all",
            False,
            id="personal-bearer",
            marks=pytest.mark.case_detail("本人用Bearerで対象を全APIとすると個別の操作選択を閉じる"),
        ),
        pytest.param(
            "system",
            "shared",
            "selected",
            True,
            id="unattended",
            marks=pytest.mark.case_detail("無人実行は対象API・操作を選べるが利用者指定を表示しない"),
        ),
    ],
)
def test_change_credential_scope(
    portal_module: Module,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    kind: str,
    scope: str,
    visible: bool,
) -> None:
    """認証方式と対象範囲を変更すると、その方式で指定できる利用者・API操作の欄を表示する。"""

    view = portal_module("components.credential_views")
    ctrl = portal_module("components.controls")
    choices: dict[str, Any] = {}
    choose = view.choose

    def track(label: str, identifier: str, options: Any, on_change: Any = None) -> Any:
        choices[identifier] = on_change
        return choose(label, identifier, options, on_change)

    monkeypatch.setattr(view, "choose", track)
    dom = render(
        view.render_form,
        {"me": member(admin=True)},
        "stock",
        options(manager=True, limit=60),
        ctrl.field,
        ctrl.btn,
        AsyncMock(),
    )[1]
    elements = {}
    for element in dom.getElementsByTagName("*"):
        identifier = element.getAttribute("id")
        if identifier:
            elements[identifier] = SimpleNamespace(
                value=element.getAttribute("value"),
                hidden=element.hasAttribute("hidden"),
                checked=element.hasAttribute("checked"),
            )
    for identifier, value in {
        "cred-mode": mode,
        "cred-kind": kind,
        "cred-scope": scope,
        "cred-actions-0": "selected",
        "cred-user-scope": "selected",
    }.items():
        elements[identifier].value = value
    elements["cred-api-0"].checked = True
    monkeypatch.setattr(view, "document", SimpleNamespace(getElementById=elements.get))
    choices["cred-mode"](SimpleNamespace(target=elements["cred-mode"]))
    for expected_mode in ("bearer", "app", "system"):
        assert elements[f"cred-note-{expected_mode}"].hidden == (expected_mode != mode)
    assert elements["cred-api-list"].hidden != visible
    assert elements["cred-people"].hidden == (mode != "app" or kind != "shared")
    if visible:
        assert not elements["cred-detail-0"].hidden and not elements["cred-ops-0"].hidden


@pytest.mark.parametrize(
    ("mode", "confirm"),
    [
        pytest.param(
            "legacy",
            True,
            id="legacy",
            marks=pytest.mark.case_detail("従来APIキーを選んで失効を確定できる"),
        ),
        pytest.param(
            "legacy",
            False,
            id="keep-legacy",
            marks=pytest.mark.case_detail("従来キーの失効を取りやめるとキーは更新されない"),
        ),
        pytest.param(
            "app", True, id="app", marks=pytest.mark.case_detail("アプリの認証情報を識別子で失効できる")
        ),
        pytest.param(
            "app",
            False,
            id="keep-app",
            marks=pytest.mark.case_detail("アプリの失効を取りやめると資格は更新されない"),
        ),
    ],
)
def test_revoke_selected_key(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch, mode: str, confirm: bool
) -> None:
    """認証情報の失効操作を確定した場合だけ、対象行の資格を失効させる。"""
    keys = portal_module("components.keys")
    ctrl = portal_module("components.controls")
    api = portal_module("apis.access")
    ui = portal_module("runtime.portal_ui")
    ui.ctx.update(
        me=member(admin=True),
        workspace=workspace([unit("stock", "在庫管理", "project")], admin=True),
        keys=[issued(mode)],
        key_assets=[{"name": "棚卸", "id": "inventory"}],
    )
    buttons = Buttons(ctrl)
    monkeypatch.setattr(keys, "btn", buttons)
    monkeypatch.setattr(keys, "load", AsyncMock())
    monkeypatch.setattr(portal_module("js").window, "confirm", lambda _: confirm, raising=False)
    revoke = AsyncMock(return_value={})
    monkeypatch.setattr(api, "delete_key", revoke)
    render(keys.keys_view)
    buttons.click("キーを失効" if mode == "legacy" else "認証情報を失効")
    if confirm:
        revoke.assert_awaited_once_with(f"key-{mode}")
    else:
        revoke.assert_not_awaited()


@pytest.mark.parametrize(
    ("field", "entered", "checked", "error_label"),
    [
        pytest.param(
            "cred-ttl",
            "61",
            {"cred-api-0", "cred-op-0-0", "cred-user-0"},
            "有効",
            id="ttl-over-cap",
            marks=pytest.mark.case_detail("有効期間がプロジェクト上限を超えたら発行を止める"),
        ),
        pytest.param(
            "cred-refresh",
            "40",
            {"cred-api-0", "cred-op-0-0", "cred-user-0"},
            "更新",
            id="invalid-refresh",
            marks=pytest.mark.case_detail("有効期間より後の更新開始を選ぶと訂正を求める"),
        ),
        pytest.param(
            "cred-scope",
            "selected",
            {"cred-op-0-0", "cred-user-0"},
            "API",
            id="missing-api",
            marks=pytest.mark.case_detail("個別APIを選ぶ設定で対象が空なら発行しない"),
        ),
        pytest.param(
            "cred-actions-0",
            "selected",
            {"cred-api-0", "cred-user-0"},
            "操作",
            id="missing-operation",
            marks=pytest.mark.case_detail("操作指定で一つも選ばない場合は対象操作の選択を求める"),
        ),
        pytest.param(
            "cred-user-scope",
            "selected",
            {"cred-api-0", "cred-op-0-0"},
            "利用者",
            id="missing-person",
            marks=pytest.mark.case_detail("利用者を指定するアプリに対象者がいなければ発行を止める"),
        ),
    ],
)
def test_correct_incomplete_credential_form(
    portal_module: Module,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    entered: str,
    checked: set[str],
    error_label: str,
) -> None:
    """発行条件が未選択・範囲外のときは訂正対象を表示し、発行要求を送らない。"""
    view = portal_module("components.credential_views")
    ctrl = portal_module("components.controls")
    api = portal_module("apis.access")
    buttons = Buttons(ctrl)
    values = {
        "credential-project": "stock",
        "cred-name": "在庫",
        "cred-kind": "shared",
        "cred-mode": "app",
        "cred-scope": "selected",
        "cred-actions-0": "selected",
        "cred-user-scope": "selected",
        "cred-ttl": "30",
        "cred-refresh": "20",
        field: entered,
    }
    submit = AsyncMock()
    monkeypatch.setattr(api, "issue", submit)
    monkeypatch.setattr(view, "val", values.__getitem__)
    monkeypatch.setattr(view, "checked", checked.__contains__)
    render(
        view.render_form,
        {"me": member(admin=True)},
        "stock",
        options(manager=True, limit=35),
        ctrl.field,
        buttons,
        AsyncMock(),
    )
    with pytest.raises(ValueError, match=error_label):
        buttons.click("認証情報を発行")
    submit.assert_not_awaited()


def test_change_expiry_updates_refresh_bounds(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """有効期間を短くすると更新開始を指定できる上限も同じ期間までに短くなる。"""

    view = portal_module("components.credential_views")
    ctrl = portal_module("components.controls")
    changed: dict[str, Any] = {}
    draw_number = view.number

    def remember_number(
        label: str,
        identifier: str,
        initial: object,
        low: int,
        high: int,
        placeholder: str = "",
        on_change: Any = None,
    ) -> Any:
        changed[identifier] = on_change
        return draw_number(label, identifier, initial, low, high, placeholder, on_change)

    monkeypatch.setattr(view, "number", remember_number)
    dom = render(
        view.render_form,
        {"me": member(admin=True)},
        "stock",
        options(manager=True, limit=60),
        ctrl.field,
        ctrl.btn,
        AsyncMock(),
    )[1]
    ttl = SimpleNamespace(value="12", max="60")
    refresh = SimpleNamespace(value=control(dom, "cred-refresh").getAttribute("value"), max="60")
    monkeypatch.setattr(
        view,
        "document",
        SimpleNamespace(getElementById={"cred-ttl": ttl, "cred-refresh": refresh}.__getitem__),
    )
    changed["cred-ttl"](SimpleNamespace(target=ttl))
    assert int(refresh.max) == 12


@pytest.mark.parametrize(
    ("active", "expected"),
    [
        pytest.param(
            True,
            "有効",
            id="active",
            marks=pytest.mark.case_detail("有効な共有キーにプロジェクト全体の呼び出し方を表示する"),
        ),
        pytest.param(
            False,
            "失効",
            id="revoked",
            marks=pytest.mark.case_detail("失効済みの共有キーを一覧で識別できる"),
        ),
    ],
)
def test_shared_legacy_key_status_and_usage(portal_module: Module, active: bool, expected: str) -> None:
    """共有キーの一覧で利用状態と対象APIを確認し、有効な間は呼び出し方を参照できる。"""
    keys = portal_module("components.keys")
    ui = portal_module("runtime.portal_ui")
    data = dict(issued("legacy", revoked=not active), kind="shared", api_ids=[], name="共同棚卸")
    ui.ctx.update(
        me=member(),
        workspace=workspace([unit("stock", "在庫管理", "project")]),
        key_assets=[],
        keys=[data],
    )
    dom = render(keys.keys_view)[1]
    row = row_with(dom, "共同棚卸")
    assert "共有" in content(row) and expected in content(row) and "在庫管理" in content(row)
    if active:
        assert row.getElementsByTagName("details")
    else:
        assert not row.getElementsByTagName("button")


def test_missing_target_on_specific_legacy_key(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """個別APIを選ぶ本人限定キーでAPIを指定し忘れた場合、選択を求めて発行を止める。"""
    page = portal_module("components.keys")
    ui = portal_module("runtime.portal_ui")
    api = portal_module("apis.access")
    controls = portal_module("components.controls")
    ui.ctx.update(
        me=member(),
        workspace=workspace([unit("stock", "在庫移行", "project")]),
        keys=[],
        key_assets=[{"name": "棚卸API", "id": "inv"}],
    )
    buttons = Buttons(controls)
    monkeypatch.setattr(page, "btn", buttons)
    values = {
        "key-name": "棚卸",
        "key-project": "stock",
        "key-kind": "personal",
        "key-scope": "selected",
    }
    monkeypatch.setattr(page, "value", values.__getitem__)
    monkeypatch.setattr(
        page, "document", SimpleNamespace(getElementById=lambda _: SimpleNamespace(checked=False))
    )
    create = AsyncMock()
    monkeypatch.setattr(api, "create_key", create)
    render(page.keys_view)
    with pytest.raises(ValueError, match="API"):
        buttons.click("キーを発行")
    create.assert_not_awaited()


def test_cancel_application_secret_rotation(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """シークレット更新を取りやめた場合は既存のクライアント資格の更新を要求しない。"""
    ui = portal_module("runtime.portal_ui")
    access = portal_module("apis.access")
    views = portal_module("components.keys")
    buttons = Buttons(portal_module("components.controls"))
    ui.ctx.update(
        me=member(),
        workspace=workspace([unit("stock", "在庫管理", "project")]),
        keys=[issued("app")],
        key_assets=[{"name": "棚卸", "id": "inventory"}],
    )
    monkeypatch.setattr(views, "btn", buttons)
    monkeypatch.setattr(portal_module("js").window, "confirm", lambda _: False, raising=False)
    rotate = AsyncMock()
    monkeypatch.setattr(access, "rotate", rotate)
    render(views.keys_view)
    buttons.click("シークレットを更新")
    rotate.assert_not_awaited()
