# 画面状態と非同期イベントを管理する。
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import Any

from apis import client
from js import document, window
from puepy import Application


class PortalApplication(Application):
    def handle_error(self, exception: Exception) -> None:
        """描画エラーを記録してフレームワークに渡す。"""
        client.report(exception, "render")
        return super().handle_error(exception)


app = PortalApplication()

ctx: dict[str, Any] = {
    "config": None,
    "me": None,
    "rows": [],
    "detail": None,
    "message": "",
    "error": False,
    "busy": False,
    "query": "",
    "filters": {
        "hours": "24",
        "minutes": "60",
        "measure": "calls",
        "unit": "",
        "asset": "",
        "project": "",
        "env": "",
        "status": "",
        "start": "",
        "end": "",
    },
    "badge": 0,
    "page": 1,
    "env": "",
    "audit_id": "",
    "audit_action": "",
    "audit_offset": 0,
}


INITIAL_STATE = deepcopy(ctx)
client.viewer = lambda: (ctx.get("me") or {}).get("subject")


def value(name: str) -> str:
    """入力値の前後の空白を除いて取得する。"""
    return str(document.getElementById(name).value).strip()


def route() -> str:
    """現在の画面パスを返す。"""
    return str(window.location.hash).lstrip("#/") or "home"


def render() -> None:
    """ポータル全体を再描画する。"""
    app.mount("#app")


def action(fn: Callable[..., Awaitable[None]], *args: Any) -> Callable[[Any], None]:
    """クリックを非同期処理に結び付ける。"""

    def clicked(event: Any) -> None:
        event.preventDefault()
        trigger = event.currentTarget
        button = trigger if getattr(trigger, "tagName", None) == "BUTTON" else None
        asyncio.ensure_future(run(fn, *args, trigger=button))

    return clicked


async def run(fn: Callable[..., Awaitable[None]], *args: Any, trigger: Any = None) -> None:
    """操作中の表示・エラー・再描画を管理する。"""
    if ctx["busy"]:
        return
    ctx.update(busy=True, message="", error=False)
    root = document.getElementById("app")
    if trigger is not None:
        trigger.setAttribute("aria-busy", "true")
    root.inert = True
    root.setAttribute("aria-busy", "true")
    try:
        await fn(*args)
    except Exception as exc:
        client.report(exc, fn.__name__)
        ctx.update(message=str(exc), error=True)
        if not client.store.getItem("access"):
            ctx["me"] = None
    finally:
        ctx["busy"] = False
        if trigger is not None:
            trigger.removeAttribute("aria-busy")
        root.inert = False
        root.removeAttribute("aria-busy")
        render()


def role_title() -> str:
    """利用者の役割名を返す。"""
    me = ctx["me"]
    return "管理者" if me["admin"] else "監査担当" if me["auditor"] else "利用者"
