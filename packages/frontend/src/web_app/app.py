# ポータルの起動と画面描画を行う。
import asyncio

import client
from js import document, window
from portal_navigation import load
from portal_session import refresh_session
from portal_shell import Portal, adapt_navigation
from portal_ui import action, app, ctx, render, run
from pyodide.ffi.wrappers import add_event_listener
from pyodide.http import pyfetch


async def poll_badge():
    while True:
        await asyncio.sleep(30)
        if not ctx["me"] or ctx["busy"] or document.hidden:
            continue
        try:
            count = (await client.api("/notifications/count"))["unread"]
            indicator = document.getElementById("unread-count")
            if indicator:
                ctx["badge"] = count
                indicator.textContent = str(count) if count else ""
                indicator.parentElement.setAttribute("aria-label", f"通知を開く（未読{count}件）")
        except Exception:
            continue


async def start():
    document.documentElement.setAttribute(
        "data-mode", window.localStorage.getItem("visual-mode") or "auto"
    )
    client.prefix = (await (await pyfetch("/entry.json")).json())["api_prefix"]
    ctx["config"] = await client.api("/config")
    await client.callback(ctx["config"])
    if client.store.getItem("access"):
        await refresh_session()


app.page()(Portal)
add_event_listener(window.matchMedia("(max-width: 780px)"), "change", adapt_navigation)
add_event_listener(window, "popstate", action(load))
render()
asyncio.ensure_future(run(start))

asyncio.ensure_future(poll_badge())
