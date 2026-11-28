"""業務操作履歴の検索欄と一覧を表示する。"""

from __future__ import annotations

from actions.audit import audit_filter, audit_page, download_audit
from content.portal_labels import ACTIONS, LABEL
from puepy import t
from runtime.portal_ui import action, ctx

from components.controls import btn, field
from components.list_layout import disclosure, download_button, result_table


def audit_search(request_id: str, selected_action: str) -> None:
    """照合条件とダウンロード操作を表示する。"""
    with t.form(classes="searchbar", on_submit=action(audit_filter)):
        field("リクエストID", "audit-id", text=request_id, placeholder="実行結果に表示されたID")
        field(
            "操作",
            "audit-action",
            options=[("", "すべての操作"), *ACTIONS.items()],
            text=selected_action,
        )
        t.button("絞り込む", type="submit", classes="btn btn-primary")


def audit_view() -> None:
    """検索結果とページ移動を表示する。"""
    with t.div(classes="list-tools"):
        with disclosure(
            "検索条件", status="絞り込み中" if ctx["audit_id"] or ctx["audit_action"] else ""
        ):
            audit_search(ctx["audit_id"], ctx["audit_action"])
        download_button("業務監査をダウンロード", action(download_audit))
    if not ctx["rows"]:
        t.p("条件に一致する記録はありません。", classes="empty")
    else:
        with result_table(
            "業務操作履歴一覧", ("記録時刻（UTC）", "操作", "実行者", "対象", "詳細", "リクエストID")
        ):
            for row in ctx["rows"][:30]:
                with t.tr():
                    t.td(row["at"][:19].replace("T", " "))
                    with t.td():
                        t.strong(ACTIONS.get(row["action"], row["action"]))
                        t.div(row["action"], classes="mono")
                    t.td(row["actor"])
                    with t.td():
                        t.div("提供元 " + row["owner"])
                        t.div(row["project"] + " " + LABEL.get(row["environment"], ""))
                        t.div("API " + row["asset_id"], classes="mono")
                        if row.get("target_subject"):
                            t.div("対象利用者 " + row["target_subject"], classes="mono")
                    t.td(row["detail"])
                    t.td(row["request_id"], classes="mono")
    with t.div(classes="pager"):
        if ctx["audit_offset"]:
            btn("新しい記録", audit_page, ctx["audit_offset"] - 30)
        if len(ctx["rows"]) > 30:
            btn("以前の記録", audit_page, ctx["audit_offset"] + 30)
