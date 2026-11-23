import asyncio

import client
from activity_filters import graph
from portal_navigation import go, load
from portal_ui import btn, ctx, role_title
from puepy import t
from screen_registry import Screen


def dashboard_view():
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
    with t.div(classes="box"):
        t.h2("業務メニュー")
        with t.div(classes="btn-grouping"):
            btn("APIを探す", go, "catalog", primary=True)
            if ctx["me"]["owners"]:
                btn("新しいAPIを登録", go, "register")
                btn("届いた申請を確認", go, "inbox")
            if ctx["me"]["admin"]:
                btn("ユーザーを管理", go, "members")
            if ctx["me"]["admin"] or ctx["me"]["owners"]:
                btn("利用者へのお知らせ", go, "notifications")
            btn("メトリクスを分析", go, "metrics")


async def load_dashboard(_page):
    results = await asyncio.gather(
        client.api("/dashboard"),
        client.api("/metrics?minutes=60"),
        client.api("/access-logs"),
        return_exceptions=True,
    )
    for key, result in zip(("dashboard", "home_metrics", "recent_logs"), results, strict=True):
        if not isinstance(result, BaseException):
            ctx[key] = result
    for result in results:
        if isinstance(result, BaseException):
            raise result


SCREENS = (
    Screen(
        "dashboard",
        "利用状況",
        dashboard_view,
        load_dashboard,
        group="ワークスペース",
        order=70,
        clear_on_load=("dashboard", "home_metrics", "recent_logs"),
    ),
)
