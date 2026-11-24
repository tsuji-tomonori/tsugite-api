# 集計条件と時系列グラフを表示する。
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from puepy import t
from routing.portal_navigation import go, load
from runtime.portal_ui import INITIAL_STATE, action, ctx, value

from components.controls import field
from components.list_layout import disclosure

MEASURES = {
    "calls": "呼び出し件数",
    "success": "成功件数",
    "errors": "エラー件数",
    "denied": "拒否件数",
    "avg_ms": "平均応答時間（ms）",
    "max_ms": "最大応答時間（ms）",
}


PERIODS = {"1": "過去1時間", "24": "過去24時間", "168": "過去7日", "720": "過去30日"}


async def apply_filters(chart: bool) -> None:
    """入力条件を適用して再読み込みする。"""
    f = {k: value("f-" + k) for k in ctx["filters"]}
    if not chart:
        ctx["access_id"] = value("access-id")
    ctx["filters"] = f
    ctx["log_offset"] = 0
    await load()


def filters_view(chart: bool, *, scope: str = "metrics") -> None:
    """現在の絞り込み条件を表示する。"""
    f = ctx["filters"]
    keys = f if chart else [k for k in f if k not in ("minutes", "measure")]
    count = sum(f[k] != INITIAL_STATE["filters"][k] for k in keys)
    request_id = "" if chart else ctx.get("access_id", "")
    period = "日時指定" if f["start"] or f["end"] else PERIODS[f["hours"]]
    status = "・".join(filter(None, (period, "絞り込み中" if count or request_id else "")))
    with disclosure("検索条件", status=status):
        if scope == "audit":
            t.p(
                "担当する部署・プロジェクトの呼び出しを確認できます。管理者と監査担当は全体を確認できます。"
            )
        filter_form(
            chart, f, ctx.get("dims", []), ctx.get("workspace", {}), scope=scope, request_id=request_id
        )


def filter_form(
    chart: bool,
    f: dict[str, str],
    dims: list[dict[str, Any]],
    workspace: dict[str, Any],
    *,
    scope: str = "metrics",
    request_id: str = "",
) -> None:
    """集計範囲を入力するフォームを描画する。"""

    def choice(k: str, title: str, opts: Sequence[tuple[str, str]]) -> None:
        field(title, "f-" + k, options=opts, text=f[k])

    with t.form(on_submit=action(apply_filters, chart)):
        with t.div(classes="filter-grid"):
            if not chart:
                field("照合するリクエストID", "access-id", text=request_id)
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
                list(PERIODS.items()),
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
        t.button("条件を適用", type="submit", classes="btn btn-primary")


async def inspect_bucket(at: str, minutes: int) -> None:
    """選択した時間帯のログを開く。"""
    begin = datetime.fromisoformat(at)
    ctx["filters"].update(start=begin.isoformat(), end=(begin + timedelta(minutes=minutes)).isoformat())
    ctx["log_offset"] = 0
    me = ctx["me"]
    await go("audit-logs" if me.get("leads") or me["admin"] or me.get("auditor") else "logs")


def graph(pts: list[dict[str, Any]], key: str, minutes: int) -> None:
    """時間帯別の集計値を棒グラフで描画する。"""
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
