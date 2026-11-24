# 利用状況の集計と直近ログを表示する。
from __future__ import annotations

from puepy import t
from routing.portal_navigation import go, load
from runtime.portal_ui import ctx, role_title

from components.activity_filters import graph
from components.controls import btn


def dashboard_view() -> None:
    """利用件数とメトリクスを表示する。"""
    summary = ctx.get("dashboard")
    t.p(role_title() + "としての利用状況", classes="subtitle")
    if summary is None:
        t.p("利用状況の件数を取得できませんでした。")
    else:
        with t.div(classes="stat-grid"):
            cards = [
                ("直近24時間の呼び出し", summary["calls"]),
                ("直近24時間のエラー", summary["errors"]),
            ]
            if ctx["me"]["owners"] or ctx["me"]["admin"]:
                cards.append(("管理対象のAPI", summary["inventory"]))
            cards.extend([("承認待ち", summary["pending"]), ("利用中の契約", summary["approved"])])
            for label, count in cards:
                with t.article(classes="stat"):
                    t.span(label)
                    t.strong(str(count))
    with t.div(classes="home-panels"):
        with t.section(classes="box"):
            t.h2("呼び出し件数の推移")
            t.p("直近24時間・1時間ごと（UTC）", classes="muted")
            data = ctx.get("home_metrics")
            if data is None:
                t.p("メトリクスを取得できませんでした。")
            else:
                graph(data["points"], "calls", data["minutes"])
            btn("メトリクスを開く", go, "metrics")
        with t.section(classes="box"):
            t.h2("自分の最近の呼び出し")
            logs = ctx.get("recent_logs")
            for row in (logs or [])[:4]:
                with t.div(classes="recent-call"):
                    t.strong(str(row["status"]))
                    t.span(row["method"] + " " + (row["operation"] or "操作未確定"))
                    t.small(row["at"][11:19] + " UTC")
            if logs is None:
                t.p("最近の呼び出しを取得できませんでした。")
            elif not logs:
                t.p("直近24時間の呼び出しはありません。", classes="muted")
            btn("アクセスログを開く", go, "logs")
    if summary is None or data is None or logs is None:
        btn("利用状況を再読み込み", load)
