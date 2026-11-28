"""現在のページの操作履歴を取得する。"""

from __future__ import annotations

from apis import activity as activity_api
from runtime.portal_ui import ctx


async def load_audit(_page: str) -> None:
    """現在のページの操作履歴を取得する。"""
    ctx["rows"] = await activity_api.audit(
        {
            "request_id": ctx["audit_id"],
            "action": ctx["audit_action"],
            "offset": ctx["audit_offset"],
            "limit": 31,
        }
    )
