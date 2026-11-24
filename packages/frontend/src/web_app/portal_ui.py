# 画面で共用する状態と入力部品を提供する。
import asyncio
from copy import deepcopy

import client
from js import document, window
from puepy import Application, t


class PortalApplication(Application):
    def handle_error(self, exception):
        client.report(exception, "render")
        return super().handle_error(exception)


app = PortalApplication()

ctx = {
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


def value(name):
    return str(document.getElementById(name).value).strip()


def route():
    return str(window.location.hash).lstrip("#/") or "home"


def render():
    app.mount("#app")


def action(fn, *args):
    def clicked(event):
        event.preventDefault()
        trigger = event.currentTarget
        button = trigger if getattr(trigger, "tagName", None) == "BUTTON" else None
        asyncio.ensure_future(run(fn, *args, trigger=button))

    return clicked


async def run(fn, *args, trigger=None):
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


def btn(label, fn, *args, primary=False):
    return t.button(
        label,
        type="button",
        classes="btn btn-primary" if primary else "btn btn-outline-secondary",
        on_click=action(fn, *args),
    )


def field(label, name, options=None, textarea=False, text="", placeholder="", required=None):
    with t.label(classes="field"):
        if required is not None:
            label += "（必須）" if required else "（任意）"
        t.span(label, id=name + "-label")
        if options is not None:
            with t.select(
                id=name, required=bool(required), aria_labelledby=name + "-label", classes="form-select"
            ):
                for key, title in options:
                    t.option(title, value=key, selected=(key == text))
        elif textarea:
            t.textarea(
                text, id=name, classes="form-control", required=bool(required), placeholder=placeholder
            )
        else:
            t.input(
                id=name,
                value=text,
                classes="form-control",
                required=bool(required),
                placeholder=placeholder,
            )


def role_title():
    me = ctx["me"]
    return (
        "管理者"
        if me["admin"]
        else "提供者"
        if me["owners"]
        else "監査担当"
        if me["auditor"]
        else "利用者"
    )
