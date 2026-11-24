# アクセスログ・監査履歴・監査履歴詳細・アクセスログ詳細の画面と操作を定義する。
from urllib.parse import parse_qs, quote, unquote, urlencode

import chat_views
import client
from access_log_display import detail_fields, timestamp
from activity_filters import filter_form, filters_view, load_dimensions, time_params
from audit_navigation import trace_lookup
from js import window
from list_layout import download_button
from portal_download import save_blob
from portal_navigation import go, load
from portal_ui import INITIAL_STATE, action, btn, ctx, render, route
from puepy import t
from pyodide.http import pyfetch
from screen_registry import Screen

PAGE_SIZE = 20


def can_audit(me):
    return bool(me.get("admin") or me.get("auditor") or me.get("leads"))


async def download_logs():
    params = {**ctx["log_period"], "request_id": ctx.get("access_id", "")}
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


async def log_page(offset):
    await fetch_log_rows(ctx["log_period"], offset)


def logs_view(scope="personal"):
    if scope == "audit" and not can_audit(ctx["me"]):
        t.p("監査履歴を閲覧する権限がありません。")
        return
    if "log_rows" not in ctx:
        t.p("ログを取得できませんでした。")
        btn("再読み込み", load)
        return
    with t.div(classes="list-tools"):
        filters_view(False, scope=scope)
        download_button("アクセスログをダウンロード", action(download_logs))
    rows = ctx["log_rows"]
    if not rows:
        t.p("条件に一致するアクセスログはありません。", classes="empty")
        return
    workspace = ctx.get("workspace", {})
    names = {u["id"]: u["name"] for u in workspace.get("units", [])}
    users = {u["subject"]: u["username"] for u in workspace.get("users", [])}
    label = "監査履歴一覧" if scope == "audit" else "アクセスログ一覧"
    with t.div(
        classes="resource-table result-table log-table", tabindex="0", role="region", aria_label=label
    ):
        with t.table(aria_label=label):
            with t.thead():
                with t.tr():
                    for title in (
                        "リクエストID",
                        *(("呼び出し主体", "利用プロジェクト") if scope == "audit" else ()),
                        "記録時刻（UTC）",
                        "操作",
                        "HTTPステータス",
                        "処理時間",
                    ):
                        t.th(title, scope="col")
            with t.tbody():
                for row in rows[:PAGE_SIZE]:
                    path = detail_path(row["request_id"], ctx["filters"]["unit"], audit=scope == "audit")
                    with t.tr(on_click=action(go, path)):
                        with t.td():
                            t.a(row["request_id"], href="#/" + path, classes="mono")
                        if scope == "audit":
                            t.td(users.get(row["actor"], row["actor"]))
                            t.td(names.get(row["project"], row["project"]) or "未記録")
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


def detail_path(request_id, unit="", view="", *, audit=False):
    params = {k: v for k, v in (("unit", unit), ("view", view)) if v}
    root = "audit-logs/" if audit else "logs/"
    return root + quote(request_id, safe="") + ("?" + urlencode(params) if params else "")


async def load_logs(page):
    scope = "audit" if page == "audit-logs" else "personal"
    if ctx.get("log_scope") != scope:
        ctx.update(log_offset=0, access_id="", log_scope=scope)
    if scope == "audit" and not can_audit(ctx["me"]):
        return
    await load_dimensions(scope)
    offset = ctx.get("log_offset", 0)
    period = ctx.get("log_period") if offset else None
    await fetch_log_rows(period or {**time_params(), "scope": scope}, offset)


async def fetch_log_rows(period, offset):
    params = {
        **period,
        "request_id": ctx.get("access_id", ""),
        "offset": offset,
        "limit": PAGE_SIZE + 1,
    }
    rows = await client.api("/access-logs?" + urlencode(params))
    if period["scope"] == ctx.get("log_scope"):
        ctx.update(log_rows=rows, log_offset=offset, log_period=period)


async def load_detail(page):
    ctx.pop("log_detail", None)
    root, _, key_query = page.partition("/")
    key, _, query = key_query.partition("?")
    params = parse_qs(query)
    request_id = unquote(key)
    unit = params.get("unit", [""])[0]
    scope = "audit" if root == "audit-logs" else "personal"
    row = await client.api(
        "/access-logs/detail?" + urlencode({"request_id": request_id, "unit": unit, "scope": scope})
    )
    if route() == page:
        ctx["log_detail"] = (page, row, unit, params.get("view", [""])[0])


def detail_view():
    audit = route().startswith("audit-logs/")
    back = "監査履歴一覧へ戻る" if audit else "アクセスログ一覧へ戻る"
    listing = "#/audit-logs" if audit else "#/logs"
    detail = ctx.get("log_detail")
    if not detail or detail[0] != route():
        t.a(back, href=listing)
        return
    path, row, unit, view = detail
    key = row["request_id"]
    if view in ("inquiry", "chat"):
        t.a("アクセスログの詳細へ戻る", href="#/" + detail_path(key, unit, audit=audit))
        chat_views.home(ctx, render, log=row, path=path, inquiry_only=view == "inquiry")
        return
    t.a(back, href=listing)
    with t.div(classes="box table-scroll log-detail"):
        with t.table(aria_label="呼び出しの詳細"):
            with t.tbody():
                for label, data in detail_fields(row):
                    with t.tr():
                        t.th(label, scope="row")
                        t.td(data)
    with t.div(classes="btn-grouping log-links"):
        for label, target in (("このIDで問い合わせる", "inquiry"), ("このIDでチャットに質問", "chat")):
            t.a(label, href="#/" + detail_path(key, unit, target, audit=audit))
        if ctx["me"]["admin"]:
            btn("対象APIを開く", go, "api/" + row["asset_id"])
        if can_audit(ctx["me"]):
            btn("業務操作履歴で照合", trace_lookup, key)


SCREENS = (
    Screen(
        "logs",
        "アクセスログ",
        logs_view,
        load_logs,
        group="ガバナンス",
        order=140,
        clear_on_load=("log_rows", "dims", "workspace"),
        examples={
            "logs": lambda: filter_form(
                False, INITIAL_STATE["filters"], [], {}, scope="personal", request_id="example-request"
            )
        },
    ),
    Screen(
        "audit-logs",
        "監査履歴",
        lambda: logs_view("audit"),
        load_logs,
        group="ガバナンス",
        order=145,
        visible=can_audit,
        clear_on_load=("log_rows", "dims", "workspace"),
    ),
    Screen(
        "audit-logs/",
        "監査履歴詳細",
        detail_view,
        load_detail,
        parent="audit-logs",
        clear_on_load=("log_detail",),
    ),
    Screen(
        "logs/",
        "アクセスログ詳細",
        detail_view,
        load_detail,
        parent="logs",
        clear_on_load=("log_detail",),
    ),
)
