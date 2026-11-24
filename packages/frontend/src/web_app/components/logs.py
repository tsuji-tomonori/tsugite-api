# アクセスログと監査履歴の一覧・詳細を表示する。
from __future__ import annotations

from actions.logs import PAGE_SIZE, can_audit, detail_path, download_logs, log_page
from content.access_log_display import detail_fields, timestamp
from puepy import t
from routing.audit_navigation import trace_lookup
from routing.portal_navigation import go, load
from runtime.portal_ui import action, ctx, render, route

from components import chat_views
from components.activity_filters import filters_view
from components.controls import btn
from components.list_layout import download_button


def logs_view(scope: str = "personal") -> None:
    """閲覧範囲に応じたアクセスログ一覧を描画する。"""
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


def detail_view() -> None:
    """選択した呼び出しの情報と関連操作を描画する。"""
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
