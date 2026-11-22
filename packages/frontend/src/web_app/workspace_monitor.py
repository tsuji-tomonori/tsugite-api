"""部署・プロジェクトの実測件数と内訳。"""

from portal_navigation import load
from portal_ui import btn, ctx
from puepy import t


def breakdown(title, rows):
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


def monitoring_view(unit, paths):
    usage = ctx.get("workspace_usage")
    if not usage or usage["unit_id"] != unit["id"]:
        t.p("利用状況を取得できませんでした。")
        btn("再読み込み", load)
        return
    with t.div(classes="results-head"):
        t.h3("利用状況")
        btn("更新", load)
    with t.div(classes="stat-grid"):
        for label, key in (("呼び出し", "calls"), ("エラー", "errors")):
            with t.div(classes="stat"):
                t.span(label)
                t.strong(f"{usage[key]:,} 件")
    with t.div(classes="usage-breakdowns"):
        breakdown("プロジェクト別の呼び出し", usage["by_project"])
        breakdown("API別の呼び出し", usage["by_api"])
    with t.details(classes="box"):
        t.summary(f"集計対象メンバー（所属 {len(usage['members'])} 件）")
        for member in usage["members"]:
            t.p(
                " · ".join(
                    filter(
                        None,
                        [
                            member.get("username") or member["subject"],
                            paths.get(member["unit_id"], member["unit_id"]),
                            member.get("title"),
                            "リーダー" if member.get("leader") else "",
                        ],
                    )
                )
            )
