"""利用申請の商品情報とフォームを表示する。"""

from __future__ import annotations

from typing import Any

from actions.application import apply
from puepy import t
from runtime.portal_ui import ctx

from components import product_views
from components.controls import btn, field


def application_page() -> None:
    """読み込み状態に応じて申請欄を表示する。"""
    a = ctx["detail"]
    if not a:
        t.p("APIを読み込み中…")
        return
    t.p(a["name"])
    t.a("APIの詳細に戻る", href="#/api/" + a["id"])
    if not a["published"]:
        t.p("このAPIは現在、新規の利用申請を受け付けていません。")
        return
    application_panel(a, ctx["me"])


def application_panel(a: dict[str, Any], me: dict[str, Any]) -> None:
    """対象と利用条件を入力する欄を組み立てる。"""
    with t.section(classes="box"):
        field(
            "利用プロジェクト",
            "project",
            required=True,
            options=[(p, p) for p in me["projects"]] + [(me["personal_project"], "個人ワークスペース")],
        )
        field(
            "申請対象",
            "grant-kind",
            required=True,
            options=[("project", "プロジェクト全員"), ("personal", "自分だけ")],
        )
        product_views.application_form(a, field)
        field("利用目的", "reason", textarea=True, required=True)
        btn("申請する", apply, a, primary=True)
