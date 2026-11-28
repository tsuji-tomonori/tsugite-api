"""カタログの検索状態を管理する。"""

from __future__ import annotations

from apis import products as products_api
from routing.portal_navigation import load
from runtime.portal_ui import ctx, value


async def search() -> None:
    """入力条件で先頭ページを検索する。"""
    ctx.update(query=value("search"), env=value("filter-env"), page=1)
    await load()


async def turn_page(n: int) -> None:
    """指定ページを開く。"""
    ctx["page"] = n
    await load()


async def load_catalog(page: str) -> None:
    """条件と閲覧権限に合う商品を取得する。"""
    params = {"inventory": str(page == "inventory").lower(), "page": ctx["page"], "q": ctx["query"]}
    if ctx["env"]:
        params["environment"] = ctx["env"]
    result = await products_api.catalog(params)
    ctx.update(
        rows=result["items"], total=result["total"], page=result["page"], size=result["page_size"]
    )
