"""部署とプロジェクトの画面を検証する。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from routing.screen_registry import Screen
from unittest.mock import AsyncMock

import pytest
from test_components import render
from test_required_people_support import content


def directory() -> dict[str, Any]:
    return {
        "admin": False,
        "my_units": ["d00"],
        "leads": ["d00"],
        "memberships": [],
        "users": [],
        "units": [
            *[
                {
                    "id": f"d{i:02}",
                    "name": f"部署{i:02}",
                    "kind": "department",
                    "parent": "",
                    "stopped": False,
                }
                for i in range(11)
            ],
            {"id": "p", "name": "計画", "kind": "project", "parent": "d00", "stopped": False},
        ],
    }


def screen(portal_module: Callable[[str], ModuleType], path: str, data: dict[str, Any]) -> Screen:
    ui = portal_module("runtime.portal_ui")
    portal_module("js").window.location = SimpleNamespace(hash="#/" + path)
    ui.ctx.update(workspace=data, me={"subject": "alice"})
    route: Screen = portal_module("routing.screen_registry").resolve(path)
    return route


def test_directory_pages_filter_before_paginating(portal_module: Callable[[str], ModuleType]) -> None:
    """部署を10件ずつ表示し、次ページとプロジェクト一覧では該当する対象だけを開ける。"""
    data = directory()
    page = screen(portal_module, "departments", data)
    _, dom = render(page.view)
    assert len(dom.getElementsByTagName("tbody")[0].getElementsByTagName("tr")) == 10
    assert "部署10" not in dom.toxml() and "計画" not in dom.toxml()
    assert 'href="#/departments/page/2"' in dom.toxml()
    page = screen(portal_module, "departments/page/2", data)
    _, dom = render(page.view)
    assert len(dom.getElementsByTagName("tbody")[0].getElementsByTagName("tr")) == 1
    assert 'href="#/departments/detail/d10"' in dom.toxml()
    page = screen(portal_module, "projects", data)
    _, dom = render(page.view)
    assert 'href="#/projects/detail/p"' in dom.toxml() and "部署00" in dom.toxml()
    assert "#/departments/detail/" not in dom.toxml()


def test_direct_members_have_aligned_table_columns(portal_module: Callable[[str], ModuleType]) -> None:
    """直接所属の利用者をユーザー名・氏名・メールアドレス・担当ロールに分け、管理者にだけ操作列を表示する。"""
    data = directory()
    data["admin"] = True
    data["users"] = [{"subject": "bob", "username": "legacy-bob"}]
    data["memberships"] = [
        {
            "subject": "alice",
            "username": "alice",
            "email": "long.alias@example.test",
            "full_name": "高橋 美咲",
            "display_name": "みさき",
            "unit_id": "p",
            "title": "在庫担当",
            "leader": True,
        },
        {"subject": "bob", "unit_id": "p", "leader": False},
        {"subject": "other", "unit_id": "d00", "leader": False},
    ]
    page = screen(portal_module, "projects/detail/p", data)
    _, dom = render(page.view)
    table = dom.getElementsByTagName("table")[0]
    assert table.getAttribute("aria-label") == "直接の所属メンバー"
    assert [header.firstChild.data for header in table.getElementsByTagName("th")] == [
        "ユーザー名",
        "氏名",
        "メールアドレス",
        "担当ロール",
        "操作",
    ]
    first, second = table.getElementsByTagName("tbody")[0].getElementsByTagName("tr")
    for row, username, name, email, role, subject in (
        (first, "alice", "高橋 美咲", "long.alias@example.test", "リーダー", "alice"),
        (second, "legacy-bob", "未登録", "—", "メンバー", "bob"),
    ):
        cells = row.getElementsByTagName("td")
        assert len(cells) == 5
        assert cells[0].firstChild.data == username
        assert cells[1].getElementsByTagName("span")[0].firstChild.data == name
        assert cells[2].firstChild.data == email
        assert cells[3].getElementsByTagName("strong")[0].firstChild.data == role
        assert cells[4].getElementsByTagName("a")[0].getAttribute("href") == (
            "#/projects/member/p/" + subject
        )
        assert cells[4].getElementsByTagName("button")[0].firstChild.data == "所属を解除"
    assert "表示名　みさき" in first.getElementsByTagName("td")[1].toxml()
    assert "在庫担当" in first.getElementsByTagName("td")[3].toxml()

    data["admin"] = False
    _, dom = render(page.view)
    table = dom.getElementsByTagName("table")[0]
    assert len(table.getElementsByTagName("th")) == 4
    assert not table.getElementsByTagName("a") and not table.getElementsByTagName("button")


def test_scoped_monitor_and_edit_routes(
    portal_module: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    """権限と種類が一致する対象だけの利用統計を取得し、管理者専用の編集フォームを分離する。"""
    data = directory()
    page = screen(portal_module, "departments/monitor/d00", data)
    usage = {
        "unit_id": "d00",
        "calls": 4,
        "errors": 1,
        "members": [],
        "by_api": [{"name": "在庫", "calls": 4}],
        "by_project": [{"project": "p", "calls": 4}],
    }
    api = AsyncMock(side_effect=[data, usage, data, data])
    monkeypatch.setattr(portal_module("apis.client"), "api", api)
    asyncio.run(portal_module("actions.workspace").load_workspace("departments/monitor/d00"))
    _, dom = render(page.view)
    assert [m.getAttribute("value") for m in dom.getElementsByTagName("meter")] == ["4", "4"]
    assert "4 件" in dom.toxml() and "1 件" in dom.toxml()
    assert "所属メンバーはいません。" in dom.toxml()
    for path in ("departments/monitor/d01", "projects/monitor/d00"):
        page = screen(portal_module, path, data)
        asyncio.run(portal_module("actions.workspace").load_workspace(path))
        _, dom = render(page.view)
        assert not dom.getElementsByTagName("meter")
    assert [c.args[0] for c in api.await_args_list].count("/workspace/units/d00/usage") == 1
    page = screen(portal_module, "departments/edit/d00", data)
    assert not render(page.view)[1].getElementsByTagName("input")
    data["admin"] = True
    _, dom = render(page.view)
    assert dom.getElementsByTagName("input")[0].getAttribute("value") == "部署00"
    assert not dom.getElementsByTagName("table") and not dom.getElementsByTagName("meter")


def test_unit_retirement_actions_are_admin_only(portal_module: Callable[[str], ModuleType]) -> None:
    """管理者にだけ移管・削除を表示し、移管先には同種の別組織だけを提示する。"""
    data = directory()
    page = screen(portal_module, "departments/detail/d00", data)
    assert "部署を削除" not in render(page.view)[1].toxml()
    data["admin"] = True
    _, dom = render(page.view)
    html = dom.toxml()
    assert "部署を移管" in html and "部署を削除" in html
    selector = next(
        s for s in dom.getElementsByTagName("select") if s.getAttribute("id") == "unit-destination"
    )
    ids = {option.getAttribute("value") for option in selector.getElementsByTagName("option")}
    assert "d01" in ids and "d00" not in ids and "p" not in ids


def test_project_monitor_shows_members_as_a_table(
    portal_module: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    """プロジェクト単位の集計であることを案内し、所属メンバーをユーザー名と氏名を含む表で表示する。"""
    data = directory()
    data["admin"] = True
    path = "projects/monitor/p"
    page = screen(portal_module, path, data)
    usage = {
        "unit_id": "p",
        "calls": 4,
        "errors": 1,
        "members": [
            {
                "subject": "alice",
                "username": "tanaka",
                "full_name": "田中 花子",
                "unit_id": "p",
                "title": "係長",
                "leader": True,
            },
            {"subject": "bob", "unit_id": "p", "title": "", "leader": False},
        ],
        "by_api": [],
        "by_project": [{"project": "p", "calls": 4}],
    }
    api = AsyncMock(side_effect=[data, usage])
    monkeypatch.setattr(portal_module("apis.client"), "api", api)
    asyncio.run(portal_module("actions.workspace").load_workspace(path))

    _, dom = render(page.view)
    assert api.await_args is not None
    assert api.await_args.args == ("/workspace/units/p/usage",)
    assert "選択したプロジェクトの利用実績を集計しています。" in dom.toxml()
    details = dom.getElementsByTagName("details")[0]
    assert details.getElementsByTagName("summary")[0].firstChild.data == "所属メンバー（2 件）"
    table = details.getElementsByTagName("table")[0]
    header = table.getElementsByTagName("thead")[0].getElementsByTagName("th")
    assert [cell.firstChild.data for cell in header] == [
        "ユーザー名",
        "氏名",
        "所属",
        "役職",
        "管理権限",
    ]
    rows = table.getElementsByTagName("tbody")[0].getElementsByTagName("tr")
    assert [
        [content(cell) for cell in row.childNodes if cell.nodeType == row.ELEMENT_NODE] for row in rows
    ] == [
        ["tanaka", "田中 花子", "部署00 / 計画", "係長", "リーダー"],
        ["bob", "未登録", "部署00 / 計画", "—", "メンバー"],
    ]
