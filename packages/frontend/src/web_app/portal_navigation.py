import asyncio

import client
from js import window
from portal_ui import ctx, route
from screen_registry import resolve


async def go(page, *, query=None):
    if query is not None or (page in ("catalog", "inventory") and page != route()):
        ctx.update(page=1, query=query or "", env="")
    if window.matchMedia("(max-width: 780px)").matches:
        ctx["nav_open"] = False
    window.history.pushState(None, "", "#/" + page)
    await load()
    window.scrollTo(0, 0)


async def load():
    if not ctx["me"]:
        return
    page = route()
    screen = resolve(page)
    if screen:
        for key in screen.clear_on_load:
            ctx.pop(key, None)
    if page != "keys":
        ctx.pop("issued_key", None)
    ctx["me"], badge = await asyncio.gather(client.api("/me"), client.api("/notifications/count"))
    ctx["badge"] = badge["unread"]
    if screen and screen.load_data:
        await screen.load_data(page)
