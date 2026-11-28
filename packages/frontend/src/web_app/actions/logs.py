"""アクセスログの取得・ページ移動・出力を扱う。"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlencode

from apis import activity as activity_api
from js import window
from runtime.portal_download import save_blob
from runtime.portal_ui import ctx, route

from actions.activity import load_dimensions, time_params

PAGE_SIZE = 20


def can_audit(me: dict[str, Any]) -> bool:
    """利用者に監査範囲があるか判定する。"""
    return bool(me.get("admin") or me.get("auditor") or me.get("leads"))


async def download_logs() -> None:
    """検索結果を最後のカーソルまでダウンロードする。"""
    params = {**ctx["log_period"], "request_id": ctx.get("access_id", "")}
    parts = window.Array.new()
    while True:
        res = await activity_api.download_chunk(params)
        if not res.ok:
            raise ValueError("ログを取得できませんでした")
        parts.push(await res.js_response.blob())
        cursor = res.js_response.headers.get("x-next-cursor")
        if not cursor:
            break
        params["cursor"] = str(cursor)
    save_blob(window.Blob.new(parts), "access-log.jsonl")


async def log_page(offset: int) -> None:
    """検索期間を保って指定位置に移動する。"""
    await fetch_log_rows(ctx["log_period"], offset)


def detail_path(request_id: str, unit: str = "", view: str = "", *, audit: bool = False) -> str:
    """監査範囲とリクエストIDを含む詳細URLを作る。"""
    params = {k: v for k, v in (("unit", unit), ("view", view)) if v}
    root = "audit-logs/" if audit else "logs/"
    return root + quote(request_id, safe="") + ("?" + urlencode(params) if params else "")


async def load_logs(page: str) -> None:
    """閲覧範囲を確認して一覧を読み込む。"""
    scope = "audit" if page == "audit-logs" else "personal"
    if ctx.get("log_scope") != scope:
        ctx.update(log_offset=0, access_id="", log_scope=scope)
    if scope == "audit" and not can_audit(ctx["me"]):
        return
    await load_dimensions(scope)
    offset = ctx.get("log_offset", 0)
    period = ctx.get("log_period") if offset else None
    await fetch_log_rows(period or {**time_params(), "scope": scope}, offset)


async def fetch_log_rows(period: dict[str, Any], offset: int) -> None:
    """指定期間と位置のログを取得する。"""
    params = {
        **period,
        "request_id": ctx.get("access_id", ""),
        "offset": offset,
        "limit": PAGE_SIZE + 1,
    }
    rows = await activity_api.logs(params)
    if period["scope"] == ctx.get("log_scope"):
        ctx.update(log_rows=rows, log_offset=offset, log_period=period)


async def load_detail(page: str) -> None:
    """遷移先のリクエスト一件を読み込む。"""
    ctx.pop("log_detail", None)
    root, _, key_query = page.partition("/")
    key, _, query = key_query.partition("?")
    params = parse_qs(query)
    request_id = unquote(key)
    unit = params.get("unit", [""])[0]
    scope = "audit" if root == "audit-logs" else "personal"
    row = await activity_api.log_detail(request_id, unit, scope)
    if route() == page:
        ctx["log_detail"] = (page, row, unit, params.get("view", [""])[0])
