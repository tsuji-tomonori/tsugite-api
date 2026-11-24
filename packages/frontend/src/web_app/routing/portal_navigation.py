# URL変更時の画面とデータを更新する。
from __future__ import annotations

import asyncio

from apis import messages as messages_api
from apis import session as session_api
from js import window
from runtime.portal_ui import ctx, route

from routing.screen_registry import resolve


async def go(page: str, *, query: str | None = None) -> None:
    """画面履歴を更新して遷移する。"""
    if query is not None or (page in ("catalog", "inventory") and page != route()):
        ctx.update(page=1, query=query or "", env="")
    if window.matchMedia("(max-width: 780px)").matches:
        ctx["nav_open"] = False
    window.history.pushState(None, "", "#/" + page)
    await load()
    window.scrollTo(0, 0)


async def load() -> None:
    """現在のURLに対応する画面データを取得する。"""
    if not ctx["me"]:
        return
    page = route()
    screen = resolve(page)
    if screen:
        for key in screen.clear_on_load:
            ctx.pop(key, None)
    if page != "keys":
        ctx.pop("issued_key", None)
    ctx["me"], badge = await asyncio.gather(session_api.me(), messages_api.unread())
    ctx["badge"] = badge["unread"]
    if screen and screen.load_data:
        await screen.load_data(page)
