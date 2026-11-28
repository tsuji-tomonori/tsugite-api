# 業務操作履歴の検索と出力を扱う。
from __future__ import annotations

import json
from datetime import datetime, timezone

from apis import activity as activity_api
from js import window
from routing.portal_navigation import load
from runtime.portal_download import save_blob
from runtime.portal_ui import ctx, value


async def audit_filter() -> None:
    """入力した検索条件で履歴を更新する。"""
    ctx.update(audit_id=value("audit-id"), audit_action=value("audit-action"), audit_offset=0)
    await load()


async def audit_page(offset: int) -> None:
    """指定位置から履歴を表示する。"""
    ctx["audit_offset"] = offset
    await load()


async def download_audit() -> None:
    """検索条件に合う全件をダウンロードする。"""
    parts = window.Array.new()
    params = {
        "action": ctx["audit_action"],
        "request_id": ctx["audit_id"],
        "limit": 250,
        "until": datetime.now(timezone.utc).isoformat(),
    }
    offset = 0
    while True:
        rows = await activity_api.audit({**params, "offset": offset})
        parts.push("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        if len(rows) < 250:
            break
        offset += len(rows)
    save_blob(window.Blob.new(parts), "audit-log.jsonl")
