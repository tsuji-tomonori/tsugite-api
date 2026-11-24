# 業務操作履歴の検索欄と一覧を表示する。
from __future__ import annotations

from actions.audit import audit_filter, audit_page, download_audit
from content.portal_labels import ACTIONS, LABEL
from puepy import t
from runtime.portal_ui import action, ctx

from components.controls import btn, field


def audit_search(request_id: str, selected_action: str) -> None:
    """照合条件とダウンロード操作を表示する。"""
    btn("業務監査をダウンロード", download_audit)
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
    audit_search(ctx["audit_id"], ctx["audit_action"])
    if not ctx["rows"]:
        t.p("条件に一致する記録はありません。", classes="empty")
    for row in ctx["rows"][:30]:
        with t.article(classes="audit-row"):
            with t.div(classes="audit-top"):
                t.strong(ACTIONS.get(row["action"], row["action"]), classes="event-type")
                t.small(row["at"][:19].replace("T", " ") + " UTC", classes="muted")
            t.p(row["action"] + " · " + row["actor"], classes="mono")
            t.p(
                "提供元 "
                + row["owner"]
                + "　"
                + row["project"]
                + "　"
                + LABEL.get(row["environment"], "")
                + "　"
                + row["detail"]
            )
            if row.get("target_subject"):
                t.p("対象利用者 " + row["target_subject"], classes="mono")
            t.small("API " + row["asset_id"] + " / リクエスト " + row["request_id"], classes="mono")
    with t.div(classes="pager"):
        if ctx["audit_offset"]:
            btn("新しい記録", audit_page, ctx["audit_offset"] - 30)
        if len(ctx["rows"]) > 30:
            btn("以前の記録", audit_page, ctx["audit_offset"] + 30)
