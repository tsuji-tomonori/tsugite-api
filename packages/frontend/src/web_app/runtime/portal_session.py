# ポータルへのログイン状態を管理する。
from __future__ import annotations

from copy import deepcopy
from urllib.parse import quote, urlencode

from apis import client
from apis import session as session_api
from js import window
from routing.portal_navigation import go, load

from runtime.portal_ui import INITIAL_STATE, ctx, value


async def refresh_session() -> None:
    """利用者情報を再取得して画面を更新する。"""
    ctx["me"] = await session_api.me()
    await load()


async def login(persona: str) -> None:
    """指定したデモ利用者でセッションを開く。"""
    token = await session_api.demo(persona)
    client.store.setItem("access", token["access_token"])
    await refresh_session()


async def logout() -> None:
    """セッションを破棄してホームへ戻る。"""
    portal_login = client.store.getItem("portal_login")
    client.store.removeItem("portal_login")
    client.store.removeItem("access")
    config = ctx["config"]
    ctx.clear()
    ctx.update(deepcopy(INITIAL_STATE), config=config)
    await go("home")
    if not config["demo"] and not portal_login:
        window.location.assign(
            ctx["config"]["domain"]
            + "/logout?"
            + urlencode(
                {
                    "client_id": ctx["config"]["client_id"],
                    "logout_uri": str(window.location.origin) + "/",
                }
            )
        )


async def login_member() -> None:
    """入力したメールアドレスでデモログインする。"""
    await login(quote(value("login-email").lower(), safe=""))
