# 利用申請の確認と審査を扱う。
from __future__ import annotations

from typing import Any

from apis import access as access_api
from apis import organization, products
from components.product_views import selected_step
from js import document
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
    if page == "inbox":
        ctx["publication_requests"] = await products.publication_requests()
        if ctx["me"].get("admin"):
            ctx["policy_directory"] = await organization.workspace()
            ctx["publication_policy"] = await products.publication_policy()


async def save_guidelines() -> None:
    """管理者が入力した承認段階を順に保存する。"""
    rows = document.getElementById("publication-steps").querySelectorAll("select")
    await products.save_publication_policy(
        {
            "guidelines": value("publication-guidelines"),
            "steps": [selected_step(rows.item(i)) for i in range(rows.length)],
        }
    )
    await load()
    ctx["message"] = "提供ガイドラインと公開承認の順番を保存しました"
