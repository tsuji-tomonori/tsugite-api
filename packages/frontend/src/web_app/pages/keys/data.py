# 所属・キー・対象商品を読み込む。
from __future__ import annotations

import asyncio

from apis import access as access_api
from apis import organization as organization_api
from runtime.portal_ui import ctx


async def load_keys(_page: str) -> None:
    """所属・キー・対象商品を読み込む。"""
    ctx["workspace"] = await organization_api.workspace()
    ctx["keys"], ctx["key_assets"] = await asyncio.gather(access_api.keys(), access_api.key_assets())
