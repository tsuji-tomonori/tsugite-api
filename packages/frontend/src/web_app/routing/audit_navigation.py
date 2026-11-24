# リクエストIDで業務操作履歴に遷移する。
from __future__ import annotations

from runtime.portal_ui import ctx

from routing.portal_navigation import go


async def trace_lookup(trace: str) -> None:
    """指定したリクエストIDを検索条件として履歴を開く。"""
    ctx.update(audit_id=trace, audit_action="", audit_offset=0)
    await go("audit")
