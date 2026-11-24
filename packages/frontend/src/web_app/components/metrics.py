# 集計結果をグラフと表で表示する。
from __future__ import annotations

from puepy import t
from routing.portal_navigation import load
from runtime.portal_ui import ctx

from components.activity_filters import (
    MEASURES,
    filters_view,
    graph,
    inspect_bucket,
)
from components.controls import btn


def metrics_view() -> None:
    """フィルター・時系列グラフ・明細表を描画する。"""
    if "workspace" in ctx and "dims" in ctx:
        filters_view(True)
    data = ctx.get("metrics")
    if data is None:
        t.p("メトリクスを取得できませんでした。")
        btn("メトリクスを再読み込み", load)
        return
    key = ctx["filters"]["measure"]
    pts = data["points"]
    with t.section(classes="box"):
        t.h2(MEASURES[key])
        t.p(
            data["start"][:16].replace("T", " ") + " ～ " + data["end"][:16].replace("T", " ") + " UTC",
            classes="muted",
        )
        if not any(p["calls"] for p in pts):
            t.p("この期間に呼び出しの記録はありません。")
        else:
            graph(pts, key, data["minutes"])
        with t.details():
            t.summary("データを表で確認")
            with t.div(classes="table-scroll"), t.table():
                with t.thead(), t.tr():
                    for title in ("期間の開始（UTC）", MEASURES[key], "記録"):
                        t.th(title)
                with t.tbody():
                    for p in pts:
                        with t.tr():
                            t.td(p["at"][:16].replace("T", " "))
                            t.td(str(p[key]))
                            with t.td():
                                btn("ログを見る", inspect_bucket, p["at"], data["minutes"])
