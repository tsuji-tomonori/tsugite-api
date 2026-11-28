"""提供者とリーダーが行う操作範囲・有効期間の設定を、画面上の選択から公開APIへの保存まで検証する。"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from test_components import render
from test_required_people_support import Buttons, Module, content, member, person


@pytest.mark.parametrize(
    ("previous", "selected", "inherit", "expected"),
    [
        pytest.param(
            {},
            {0},
            False,
            ["GET /items"],
            id="read-only",
            marks=pytest.mark.case_detail("個別制限を設け、参照操作だけを保存する"),
        ),
        pytest.param(
            {"anna": ["GET /items"]},
            set(),
            False,
            [],
            id="clear-all",
            marks=pytest.mark.case_detail("選択をすべて外して保存すると個別許可は0件になる"),
        ),
        pytest.param(
            {"anna": []},
            set(),
            True,
            None,
            id="inherit",
            marks=pytest.mark.case_detail("個別設定を解除して利用申請の許可範囲を継承する"),
        ),
    ],
)
def test_person_operation_policy(
    portal_module: Module,
    monkeypatch: pytest.MonkeyPatch,
    previous: dict[str, list[str]],
    selected: set[int],
    inherit: bool,
    expected: list[str] | None,
) -> None:
    """対象者を選んで許可操作の保存または継承を選ぶと、該当する利用者とAPIに変更を適用する。"""
    view = portal_module("components.operation_views")
    api = portal_module("apis.products")
    ctrl = portal_module("components.controls")
    buttons = Buttons(ctrl)
    state = {
        "me": member(provider=True),
        "op_policy": {
            "operations": ["GET /items", "POST /items"],
            "members": [person("anna", "香織", "kaori@example.test")],
            "permissions": previous,
        },
    }
    asset = {"id": "stock", "owner": "supply", "name": "在庫照会"}

    def element(name: str) -> Any:
        if name == "op-person":
            return SimpleNamespace(value="anna")
        return SimpleNamespace(checked=any(name == f"op-allow-{i}" for i in selected))

    monkeypatch.setattr(view, "document", SimpleNamespace(getElementById=element))
    save = AsyncMock(return_value={})
    monkeypatch.setattr(api, "save_operations", save)
    reload = AsyncMock()
    render(view.provider_view, asset, state, ctrl.field, buttons, reload)
    buttons.click("権限を表示")
    dom = render(view.provider_view, asset, state, ctrl.field, buttons, reload)[1]
    assert "香織" in content(dom) and "GET /items" in content(dom) and "POST /items" in content(dom)
    buttons.click("個別設定を解除して継承" if inherit else "選んだ操作を保存")
    save.assert_awaited_once_with("stock", {"subject": "anna", "operations": expected})


@pytest.mark.parametrize(
    ("before", "choice", "expected"),
    [
        pytest.param(
            None,
            "19",
            19,
            id="shorter",
            marks=pytest.mark.case_detail("上位から継承していた有効期間に19分の上限を設定する"),
        ),
        pytest.param(
            25,
            "",
            None,
            id="inherit",
            marks=pytest.mark.case_detail("個別上限を空欄に戻し上位組織の上限を継承する"),
        ),
    ],
)
def test_project_token_limit(
    portal_module: Module,
    monkeypatch: pytest.MonkeyPatch,
    before: int | None,
    choice: str,
    expected: int | None,
) -> None:
    """プロジェクトのトークン上限を開き、上位上限を確認して個別上限の設定・解除ができる。"""
    view = portal_module("components.credential_views")
    ctrl = portal_module("components.controls")
    api = portal_module("apis.access")
    controls = Buttons(ctrl)
    state = {"me": member(admin=True)}
    reload = AsyncMock()
    limits = AsyncMock(return_value={"max_minutes": before, "inherited_minutes": 40})
    save = AsyncMock(return_value={"max_minutes": expected, "inherited_minutes": 40})
    monkeypatch.setattr(api, "limits", limits)
    monkeypatch.setattr(api, "save_limits", save)
    monkeypatch.setattr(view, "val", lambda key: choice)

    def draw() -> None:
        view.limit_view(state, ctrl.field, controls, reload, kind="project", identifier="stock")

    render(draw)
    controls.click("アクセストークンの上限を設定")
    dom = render(draw)[1]
    assert "40分" in content(dom)
    controls.click("有効期限の上限を保存")
    assert limits.await_args is not None and save.await_args is not None
    endpoint = limits.await_args.args[0]
    assert "stock" in endpoint and "project" in endpoint
    save.assert_awaited_once_with(endpoint, {"max_minutes": expected})
