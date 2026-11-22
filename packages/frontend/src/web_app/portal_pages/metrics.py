from urllib.parse import urlencode

import client
from activity_filters import MEASURES, filters_view, graph, inspect_bucket, load_dimensions, time_params
from portal_navigation import load
from portal_ui import btn, ctx
from puepy import t
from screen_registry import Screen


def metrics_view():
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


async def load_metrics(_page):
    await load_dimensions()
    params = time_params()
    ctx["metrics"] = await client.api(
        "/metrics?" + urlencode({**params, "minutes": ctx["filters"]["minutes"]})
    )


SCREENS = (
    Screen(
        "metrics",
        "メトリクス",
        metrics_view,
        load_metrics,
        group="ガバナンス",
        order=130,
        clear_on_load=("metrics",),
    ),
)
