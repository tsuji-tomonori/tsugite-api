# 利用申請の確認と審査を扱う。
from __future__ import annotations

from typing import Any

from apis import access as access_api
from routing.portal_navigation import load
from runtime.portal_ui import ctx, value


async def decide(row: dict[str, Any], decision: str) -> None:
    """選択した申請に判断結果を記録する。"""
    await access_api.review(
        row["id"],
        {"action": decision, "revision": row["revision"], "reason": value("reason-" + row["id"])},
    )
    await load()
    ctx["message"] = "申請状態を更新しました"


async def load_requests(page: str) -> None:
    """提出済みまたは受信した申請を取得する。"""
    ctx["rows"] = await access_api.request_list(page == "inbox")
