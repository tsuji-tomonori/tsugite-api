from urllib.parse import parse_qs, quote, unquote, urlencode

import chat_views
import client
from access_log_display import detail_fields, timestamp
from activity_filters import filters_view, load_dimensions, time_params
from audit_navigation import trace_lookup
from js import window
from portal_download import save_blob
from portal_navigation import go, load
from portal_ui import action, btn, ctx, field, render, route, value
from puepy import t
from pyodide.http import pyfetch
from screen_registry import Screen

PAGE_SIZE = 20


async def download_logs():
    params = {**(ctx.get("log_period") or time_params()), "request_id": ctx.get("access_id", "")}
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


def logs_view():
    filters_view(False)
    with t.div(classes="box"):
        field("照合するリクエストID", "access-id", text=ctx.get("access_id", ""))
        with t.div(classes="btn-grouping"):
            btn("IDで検索", log_lookup)
            btn("アクセスログをダウンロード", download_logs)
    rows = ctx.get("log_rows", [])
    if not rows:
        t.p("条件に一致するアクセスログはありません。", classes="empty")
        return
    with t.div(classes="box table-scroll log-table"):
        with t.table(aria_label="アクセスログ一覧"):
            with t.thead():
                with t.tr():
                    for title in (
                        "リクエストID",
                        "記録時刻（UTC）",
                        "操作",
                        "HTTPステータス",
                        "処理時間",
                    ):
                        t.th(title, scope="col")
            with t.tbody():
                for row in rows[:PAGE_SIZE]:
                    path = detail_path(row["request_id"], ctx["filters"]["unit"])
                    with t.tr(on_click=action(go, path)):
                        with t.td():
                            t.a(row["request_id"], href="#/" + path, classes="mono")
                        t.td(timestamp(row["at"]).removesuffix(" UTC"))
                        t.td(row["method"] + " " + (row["operation"] or "未記録"))
                        t.td(str(row["status"]))
                        t.td(f"{row['duration_ms']} ms")
    offset = ctx.get("log_offset", 0)
    with t.nav(classes="pager", aria_label="アクセスログのページ"):
        if offset:
            btn("前へ", log_page, max(0, offset - PAGE_SIZE))
        t.span(f"{offset + 1}～{offset + min(len(rows), PAGE_SIZE)}件", role="status")
        if len(rows) > PAGE_SIZE:
            btn("次へ", log_page, offset + PAGE_SIZE)


def detail_path(request_id, unit="", view=""):
    params = {k: v for k, v in (("unit", unit), ("view", view)) if v}
    return "logs/" + quote(request_id, safe="") + ("?" + urlencode(params) if params else "")


async def load_logs(_page):
    await load_dimensions()
    offset = ctx.get("log_offset", 0)
    if not offset or not ctx.get("log_period"):
        ctx["log_period"] = time_params()
    params = {
        **ctx["log_period"],
        "request_id": ctx.get("access_id", ""),
        "offset": offset,
        "limit": PAGE_SIZE + 1,
    }
    ctx["log_rows"] = await client.api("/access-logs?" + urlencode(params))


async def load_detail(page):
    ctx.pop("log_detail", None)
    key, _, query = page.removeprefix("logs/").partition("?")
    params = parse_qs(query)
    request_id = unquote(key)
    unit = params.get("unit", [""])[0]
    row = await client.api("/access-logs/detail?" + urlencode({"request_id": request_id, "unit": unit}))
    if route() == page:
        ctx["log_detail"] = (page, row, unit, params.get("view", [""])[0])


def detail_view():
    detail = ctx.get("log_detail")
    if not detail or detail[0] != route():
        t.a("アクセスログ一覧へ戻る", href="#/logs")
        return
    path, row, unit, view = detail
    key = row["request_id"]
    if view in ("inquiry", "chat"):
        t.a("アクセスログの詳細へ戻る", href="#/" + detail_path(key, unit))
        chat_views.home(ctx, render, log=row, path=path, inquiry_only=view == "inquiry")
        return
    t.a("アクセスログ一覧へ戻る", href="#/logs")
    with t.div(classes="box table-scroll log-detail"):
        with t.table(aria_label="呼び出しの詳細"):
            with t.tbody():
                for label, data in detail_fields(row):
                    with t.tr():
                        t.th(label, scope="row")
                        t.td(data)
    with t.div(classes="btn-grouping log-links"):
        for label, target in (("このIDで問い合わせる", "inquiry"), ("このIDでチャットに質問", "chat")):
            t.a(label, href="#/" + detail_path(key, unit, target))
        if ctx["me"]["admin"]:
            btn("対象APIを開く", go, "api/" + row["asset_id"])
        if ctx["me"]["admin"] or ctx["me"].get("auditor"):
            btn("監査履歴で照合", trace_lookup, key)


SCREENS = (
    Screen("logs", "アクセスログ", logs_view, load_logs, group="ガバナンス", order=140),
    Screen(
        "logs/",
        "アクセスログ詳細",
        detail_view,
        load_detail,
        parent="logs",
        clear_on_load=("log_detail",),
    ),
)
