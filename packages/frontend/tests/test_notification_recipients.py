# 通知先の名前と識別子の対応を検証する。
from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

from test_components import render


def test_notification_recipient_dropdown_uses_display_names(
    portal_module: Callable[[str], ModuleType],
) -> None:
    """管理者と提供者の通知先には登録された名称を表示し、送信には識別子を使う。"""
    page = portal_module("components.notifications")
    label = "営業部 / 受注から出荷までの納期改善"
    page.ctx.update(
        notices={"items": []},
        me={
            "admin": True,
            "known_projects": ["finance", "supply"],
            "known_project_labels": {"finance": label, "supply": "名称未登録（supply）"},
        },
    )
    _, dom = render(page.notices_view)
    assert [
        (o.getAttribute("value"), o.firstChild.data) for o in dom.getElementsByTagName("option")
    ] == [
        ("*", "全プロジェクト"),
        ("finance", label),
        ("supply", "名称未登録（supply）"),
    ]

    page.ctx.update(
        me={"admin": False, "owners": ["supply"]},
        targets=[
            {
                "id": "stock/finance/sandbox",
                "name": "在庫照会",
                "project": "finance",
                "project_label": label,
                "environment": "sandbox",
            }
        ],
    )
    _, dom = render(page.notices_view)
    option = dom.getElementsByTagName("option")[0]
    assert option.getAttribute("value") == "stock/finance/sandbox"
    assert option.firstChild.data == f"在庫照会 · {label} · 検証"
