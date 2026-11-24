# 商品詳細と公開状態を管理する。
from __future__ import annotations

import asyncio
from typing import Any

from apis import access as access_api
from apis import organization as organization_api
from apis import products as products_api
from routing.portal_navigation import load
from runtime.portal_ui import ctx


async def publication(asset: dict[str, Any]) -> None:
    """商品の公開状態を切り替える。"""
    await products_api.publication(asset["id"], not asset["published"])
    await load()
    ctx["message"] = "掲載状態を更新しました"


async def load_listing(page: str) -> None:
    """詳細・権限・利用申請を読み込む。"""
    ctx["detail"] = None
    ctx["detail"] = await products_api.asset(page.split("/", 1)[1])
    ctx["keys"] = await access_api.keys()
    if ctx["detail"]["owner"] in ctx["me"]["owners"]:
        ctx["op_policy"] = await products_api.operations(ctx["detail"]["id"])
        ctx["policy"], ctx["policy_directory"] = await asyncio.gather(
            products_api.policy(ctx["detail"]["id"]), organization_api.workspace()
        )
    ctx["rights"] = await access_api.asset_requests(ctx["detail"]["id"])
