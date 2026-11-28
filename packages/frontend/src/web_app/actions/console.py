# APIクライアントの選択状態を管理する。
from __future__ import annotations

import asyncio

from apis import access as access_api
from apis import products as products_api
from apis.manual import selectable_key
from runtime.portal_ui import ctx, value


async def load_console(page: str) -> None:
    """利用できる申請と認証情報を読み込む。"""
    ctx.update(console_asset=None, console_operation="", console_rights=[], console_keys=[], manual_keys={})
    rights, keys = await asyncio.gather(access_api.requests(), access_api.keys())
    ctx["console_rights"] = [r for r in rights if r["status"] == "approved"]
    ctx["console_keys"] = [k for k in keys if k.get("mode") in ("app", "bearer")]
    ctx["manual_keys"] = {k["id"]: k for k in keys if selectable_key(k, ctx["me"])}
    if key := page.partition("/")[2]:
        await open_asset(key)


async def select_asset() -> None:
    """選択した商品に切り替える。"""
    await open_asset(value("console-asset"))


async def open_asset(key: str) -> None:
    """承認済み商品の仕様を取得する。"""
    ctx.update(console_asset=None, console_operation="")
    if key and any(r["asset_id"] == key for r in ctx["console_rights"]):
        ctx["console_asset"] = await products_api.asset(key)


async def select_operation() -> None:
    """選択した操作を記録する。"""
    ctx["console_operation"] = value("console-operation")
