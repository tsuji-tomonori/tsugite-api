import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from test_components import render


def directory():
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


def screen(portal_module, path, data):
    module = portal_module("portal_pages.workspace")
    portal_module("js").window.location = SimpleNamespace(hash="#/" + path)
    module.ctx.update(workspace=data, me={"subject": "alice"})
    return module


def test_directory_pages_filter_before_paginating(portal_module):
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


def test_scoped_monitor_and_edit_routes(portal_module, monkeypatch):
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
    monkeypatch.setattr(page.client, "api", api)
    asyncio.run(page.load_workspace("departments/monitor/d00"))
    _, dom = render(page.view)
    assert [m.getAttribute("value") for m in dom.getElementsByTagName("meter")] == ["4", "4"]
    assert "4 件" in dom.toxml() and "1 件" in dom.toxml()
    for path in ("departments/monitor/d01", "projects/monitor/d00"):
        screen(portal_module, path, data)
        asyncio.run(page.load_workspace(path))
        _, dom = render(page.view)
        assert not dom.getElementsByTagName("meter")
    assert [c.args[0] for c in api.await_args_list].count("/workspace/units/d00/usage") == 1
    screen(portal_module, "departments/edit/d00", data)
    assert not render(page.view)[1].getElementsByTagName("input")
    data["admin"] = True
    _, dom = render(page.view)
    assert dom.getElementsByTagName("input")[0].getAttribute("value") == "部署00"
    assert not dom.getElementsByTagName("table") and not dom.getElementsByTagName("meter")
