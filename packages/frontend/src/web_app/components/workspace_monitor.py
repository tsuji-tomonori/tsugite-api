# 組織の利用件数と内訳を表示する。
from __future__ import annotations

from typing import Any

from puepy import t
from routing.portal_navigation import load
from runtime.portal_ui import ctx

from components.controls import btn


def breakdown(title: str, rows: list[dict[str, Any]]) -> None:
    """対象別の件数内訳を表示する。"""
    with t.section(classes="box"):
        t.h3(title)
        if not rows:
            t.p("呼び出しの記録はありません。")
            return
        maximum = max(1, max(item["calls"] for item in rows))
        with t.ul(classes="usage-bars"):
            for item in sorted(rows, key=lambda r: -r["calls"]):
                name = item.get("name") or item.get("project") or item.get("asset_id") or "未設定"
                calls = item["calls"]
                with t.li():
                    t.span(name)
                    t.span(f"{calls:,} 件", classes="usage-count")
                    t.meter(
                        min="0", max=str(maximum), value=str(calls), aria_label=f"{name}の呼び出し件数"
                    )


def monitoring_view(unit: dict[str, Any], paths: dict[str, str]) -> None:
    """組織の利用実績と集計対象メンバーを描画する。"""
    usage = ctx.get("workspace_usage")
    if not usage or usage["unit_id"] != unit["id"]:
        t.p("利用状況を取得できませんでした。")
        btn("再読み込み", load)
        return
    with t.div(classes="results-head"):
        t.h3("利用状況")
        btn("更新", load)
    scope = "プロジェクト" if unit["kind"] == "project" else "部署"
    t.p(f"選択した{scope}の利用実績を集計しています。")
    with t.div(classes="stat-grid"):
        for label, key in (("呼び出し", "calls"), ("エラー", "errors")):
            with t.div(classes="stat"):
                t.span(label)
                t.strong(f"{usage[key]:,} 件")
    with t.div(classes="usage-breakdowns"):
        breakdown("プロジェクト別の呼び出し", usage["by_project"])
        breakdown("API別の呼び出し", usage["by_api"])
    members = usage["members"]
    with t.details(classes="box"):
        t.summary(f"所属メンバー（{len(members)} 件）")
        if not members:
            t.p("所属メンバーはいません。")
            return
        with t.div(classes="resource-table", tabindex="0", role="region", aria_label="所属メンバー一覧"):
            with t.table(aria_label="所属メンバー一覧"):
                with t.thead():
                    with t.tr():
                        for title in ("ユーザー名", "所属", "役職", "管理権限"):
                            t.th(title, scope="col")
                with t.tbody():
                    for member in members:
                        with t.tr():
                            t.th(member.get("username") or member["subject"], scope="row")
                            t.td(paths.get(member["unit_id"], member["unit_id"]))
                            t.td(member.get("title") or "—")
                            t.td("リーダー" if member.get("leader") else "メンバー")
