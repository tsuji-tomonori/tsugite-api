from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import client
from portal_navigation import go, load
from portal_ui import action, btn, ctx, field, value
from puepy import t

MEASURES = {
    "calls": "呼び出し件数",
    "success": "成功件数",
    "errors": "エラー件数",
    "denied": "拒否件数",
    "avg_ms": "平均応答時間（ms）",
    "max_ms": "最大応答時間（ms）",
}


def time_params():
    f = ctx["filters"]
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=int(f["hours"]))
    return {
        k: v
        for k, v in {
            "start": f["start"] or start.isoformat(),
            "end": f["end"] or end.isoformat(),
            "unit": f["unit"],
            "asset_id": f["asset"],
            "project": f["project"],
            "environment": f["env"],
            "status": f["status"],
        }.items()
        if v
    }


async def apply_filters():
    f = {k: value("f-" + k) for k in ctx["filters"]}
    ctx["filters"] = f
    ctx["log_offset"] = 0
    await load()


def filters_view(chart, *, scope="metrics"):
    filter_form(chart, ctx["filters"], ctx.get("dims", []), ctx.get("workspace", {}), scope=scope)


def filter_form(chart, f, dims, workspace, *, scope="metrics"):

    def choice(k, title, opts):
        field(title, "f-" + k, options=opts, text=f[k])

    with t.div(classes="box"):
        with t.div(classes="filter-grid"):
            choices = [
                (u["id"], u["name"])
                for u in workspace.get("units", [])
                if u["id"] in workspace.get("leads", [])
                or (
                    scope == "audit"
                    and ctx["me"].get("auditor")
                    and u["kind"] in ("department", "project")
                )
            ]
            if choices and scope != "personal":
                choice("unit", "集計する部署・プロジェクト", [("", "閲覧できる全範囲")] + choices)
            else:
                t.input(type="hidden", id="f-unit", value="")
            choice(
                "hours",
                "期間",
                [("1", "過去1時間"), ("24", "過去24時間"), ("168", "過去7日"), ("720", "過去30日")],
            )
            choice(
                "asset", "対象API", [("", "すべて")] + sorted({(v["asset_id"], v["name"]) for v in dims})
            )
            choice(
                "project",
                "利用プロジェクト",
                [("", "すべて")] + sorted({(v["project"], v["project"]) for v in dims if v["project"]}),
            )
            choice(
                "env",
                "対象環境",
                [("", "すべて"), ("sandbox", "検証"), ("staging", "準本番"), ("production", "本番")],
            )
            field("HTTPステータス", "f-status", text=f["status"], placeholder="すべて")
            if chart:
                choice("minutes", "集計間隔", [(str(n), str(n) + "分") for n in (1, 5, 15, 60, 1440)])
                choice("measure", "表示指標", list(MEASURES.items()))
            else:
                t.input(type="hidden", id="f-minutes", value=f["minutes"])
                t.input(type="hidden", id="f-measure", value=f["measure"])
        with t.details():
            t.summary("日時を指定（UTC）")
            field("開始日時", "f-start", text=f["start"], placeholder="2026-11-21T00:00:00Z")
            field("終了日時", "f-end", text=f["end"], placeholder="2026-11-21T01:00:00Z")
        btn("条件を適用", apply_filters, primary=True)


async def inspect_bucket(at, minutes):
    begin = datetime.fromisoformat(at)
    ctx["filters"].update(start=begin.isoformat(), end=(begin + timedelta(minutes=minutes)).isoformat())
    ctx["log_offset"] = 0
    me = ctx["me"]
    await go("audit-logs" if me.get("leads") or me["admin"] or me.get("auditor") else "logs")


def graph(pts, key, minutes):
    maximum = max([1] + [p[key] for p in pts])
    t.small("最大目盛 " + str(maximum))
    with t.div(
        classes="chart-scroll", role="region", aria_label="時間帯別の" + MEASURES[key], tabindex="0"
    ):
        with t.div(classes="chart-series", style=f"--buckets:{len(pts)}"):
            with t.div(classes="time-chart"):
                for p in pts:
                    label = p["at"][:16] + " UTC · " + str(p[key])
                    t.button(
                        "",
                        type="button",
                        title=label,
                        aria_label=label,
                        classes="time-bar",
                        style=f"--height:{100 * p[key] / maximum:.2f}%",
                        on_click=action(inspect_bucket, p["at"], minutes),
                    )
            with t.div(classes="chart-axis"):
                for p in (pts[0], pts[len(pts) // 2], pts[-1]):
                    t.span(p["at"][5:16].replace("T", " "))


async def load_dimensions(scope="metrics"):
    ctx["workspace"] = await client.api("/workspace")
    allowed = ctx["workspace"]["leads"]
    if scope == "audit" and ctx["me"].get("auditor"):
        allowed = [u["id"] for u in ctx["workspace"]["units"] if u["kind"] in ("department", "project")]
    if scope == "personal" or ctx["filters"]["unit"] not in allowed:
        ctx["filters"]["unit"] = ""
    params = {"unit": ctx["filters"]["unit"]}
    path = "/metric-dimensions"
    if scope != "metrics":
        path = "/access-logs/dimensions"
        params["scope"] = scope
    ctx["dims"] = await client.api(path + "?" + urlencode(params))
