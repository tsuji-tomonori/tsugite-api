from urllib.parse import urlencode

import client
from activity_filters import filters_view, load_dimensions, time_params
from audit_navigation import trace_lookup
from js import window
from portal_download import save_blob
from portal_navigation import go, load
from portal_ui import btn, ctx, field, value
from puepy import t
from pyodide.http import pyfetch
from screen_registry import Screen


async def download_logs():
    params = {**time_params(), "request_id": ctx.get("access_id", "")}
    parts = window.Array.new()
    while True:
        res = await pyfetch(
            client.prefix + "/access-logs/download?" + urlencode(params),
            headers={
                **client.screen_headers(),
                "Authorization": "Bearer " + str(client.store.getItem("access")),
            },
        )
        if not res.ok:
            raise ValueError("ログを取得できませんでした")
        parts.push(await res.js_response.blob())
        cursor = res.js_response.headers.get("x-next-cursor")
        if not cursor:
            break
        params["cursor"] = str(cursor)
    save_blob(window.Blob.new(parts), "access-log.jsonl")


async def log_lookup():
    ctx.update(access_id=value("access-id"), log_offset=0)
    await load()


async def log_page(offset):
    ctx["log_offset"] = offset
    await load()


def request_lookup(request_id):
    with t.div(classes="box"):
        field("照合するリクエストID", "access-id", text=request_id)
        with t.div(classes="btn-grouping"):
            btn("IDで検索", log_lookup)
            btn("アクセスログをダウンロード", download_logs)


def logs_view():
    filters_view(False)
    request_lookup(ctx.get("access_id", ""))
    rows = ctx["log_rows"]
    if not rows:
        t.p("条件に一致するアクセスログはありません。", classes="empty")
    for row in rows:
        with t.article(classes="audit-row"):
            t.strong(f"{row['status']}　{row['method']} {row['operation']}")
            t.p(
                f"{row['at'][:19]} UTC　{row['actor']}　{row['project']}　{row['environment']}　{row['duration_ms']} ms"
            )
            t.small("リクエストID　" + row["request_id"], classes="mono")
            if row.get("key_id"):
                t.small("キーID　" + row["key_id"], classes="mono")
            btn("対応する業務監査", trace_lookup, row["request_id"])
            if ctx["me"]["admin"]:
                btn("対象APIを開く", go, "api/" + row["asset_id"])
    if ctx.get("log_offset", 0):
        btn("前の50件", log_page, ctx["log_offset"] - 50)
    if len(rows) == 50:
        btn("次の50件", log_page, ctx.get("log_offset", 0) + 50)


async def load_logs(_page):
    await load_dimensions()
    params = time_params()
    ctx["log_rows"] = await client.api(
        "/access-logs?"
        + urlencode(
            {
                **params,
                "request_id": ctx.get("access_id", ""),
                "offset": ctx.get("log_offset", 0),
            }
        )
    )


SCREENS = (
    Screen(
        "logs",
        "アクセスログ",
        logs_view,
        load_logs,
        group="ガバナンス",
        order=140,
        examples={"logs": lambda: request_lookup("example-request")},
    ),
)
