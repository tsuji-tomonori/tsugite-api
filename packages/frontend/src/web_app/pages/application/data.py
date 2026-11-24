# 対象商品の申請条件を読み込む。
from __future__ import annotations

from apis import products as products_api
from runtime.portal_ui import ctx


async def load_application(page: str) -> None:
    """対象商品の申請条件を読み込む。"""
    ctx["detail"] = None
    ctx["detail"] = await products_api.asset(page.split("/", 1)[1])
