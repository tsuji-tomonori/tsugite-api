"""ブラウザーでポータルを起動する。"""

from __future__ import annotations

import asyncio

from apis import client
from apis import messages as messages_api
from apis import session as session_api
from apis.invocation import fetch
from js import document, window
from pyodide.ffi.wrappers import add_event_listener
from routing.portal_navigation import load
from runtime.portal_session import refresh_session
from runtime.portal_shell import Portal, adapt_navigation
from runtime.portal_ui import action, app, ctx, render, run


async def poll_badge() -> None:
    """画面が表示されている間に未読件数を更新する。"""
    while True:
        await asyncio.sleep(30)
        if not ctx["me"] or ctx["busy"] or document.hidden:
            continue
        try:
            count = (await messages_api.unread())["unread"]
            indicator = document.getElementById("unread-count")
            if indicator:
                ctx["badge"] = count
                indicator.textContent = str(count) if count else ""
                indicator.parentElement.setAttribute("aria-label", f"通知を開く（未読{count}件）")
        except Exception:
            continue


async def start() -> None:
    """表示モードと認証状態を復元する。"""
    document.documentElement.setAttribute(
        "data-mode", window.localStorage.getItem("visual-mode") or "auto"
    )
    client.prefix = (await (await fetch("/entry.json")).json())["api_prefix"]
    ctx["config"] = await session_api.config()
    await client.callback(ctx["config"])
    if client.store.getItem("access"):
        await refresh_session()


app.page()(Portal)
add_event_listener(window.matchMedia("(max-width: 780px)"), "change", adapt_navigation)
add_event_listener(window, "popstate", action(load))
render()
asyncio.ensure_future(run(start))

asyncio.ensure_future(poll_badge())
