from copy import deepcopy
from urllib.parse import quote, urlencode

import client
import login_views
from js import window
from portal_navigation import go, load
from portal_ui import INITIAL_STATE, action, btn, ctx, field, value
from puepy import t


async def refresh_session():
    ctx["me"] = await client.api("/me")
    await load()


async def login(persona):
    token = await client.api("/demo/" + persona, "POST")
    client.store.setItem("access", token["access_token"])
    await refresh_session()


async def logout():
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


def login_page():
    if ctx["config"]["demo"]:
        t.h1("継手APIにログイン")
        t.p("ローカルで試す役割を選んでください。", classes="muted")
        with t.div(classes="btn-grouping"):
            for key, title in [
                ("provider", "提供チーム"),
                ("consumer", "利用チーム"),
                ("auditor", "監査担当"),
                ("admin", "管理者"),
            ]:
                btn(title, login, key, primary=key == "consumer")
        with t.details():
            t.summary("追加したユーザーでログイン")
            field("登録メールアドレス", "login-email")
            btn("このユーザーでログイン", login_member)
    else:
        login_views.portal_form(ctx, action, client.store, refresh_session)


async def login_member():
    await login(quote(value("login-email").lower(), safe=""))
