import json
from datetime import datetime, timezone
from urllib.parse import urlencode

import client
from js import window
from portal_download import save_blob
from portal_labels import ACTIONS, LABEL
from portal_navigation import load
from portal_ui import action, btn, ctx, field, value
from puepy import t
from screen_registry import Screen


async def audit_filter():
    ctx.update(audit_id=value("audit-id"), audit_action=value("audit-action"), audit_offset=0)
    await load()


async def audit_page(offset):
    ctx["audit_offset"] = offset
    await load()


def audit_search(request_id, selected_action):
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


def audit_view():
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


async def download_audit():
    parts = window.Array.new()
    params = {
        "action": ctx["audit_action"],
        "request_id": ctx["audit_id"],
        "limit": 250,
        "until": datetime.now(timezone.utc).isoformat(),
    }
    offset = 0
    while True:
        rows = await client.api("/audit?" + urlencode({**params, "offset": offset}))
        parts.push("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        if len(rows) < 250:
            break
        offset += len(rows)
    save_blob(window.Blob.new(parts), "audit-log.jsonl")


async def load_audit(_page):
    ctx["rows"] = await client.api(
        "/audit?"
        + urlencode(
            {
                "request_id": ctx["audit_id"],
                "action": ctx["audit_action"],
                "offset": ctx["audit_offset"],
                "limit": 31,
            }
        )
    )


SCREENS = (
    Screen(
        "audit",
        "業務操作履歴",
        audit_view,
        load_audit,
        group="ガバナンス",
        order=160,
        examples={"audit": lambda: audit_search("", "approve")},
        description="公開、申請、判断、呼び出しの記録を追跡できます。",
    ),
)
