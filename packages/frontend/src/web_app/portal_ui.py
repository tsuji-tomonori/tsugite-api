import asyncio
from copy import deepcopy

import client
from js import document, window
from puepy import Application, t


app = Application()


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
    "trial": "",
    "trace": "",
    "page": 1,
    "env": "",
    "audit_id": "",
    "audit_action": "",
    "audit_offset": 0,
}


INITIAL_STATE = deepcopy(ctx)


def value(name):
    return str(document.getElementById(name).value).strip()


def route():
    return str(window.location.hash).lstrip("#/") or "home"


def render():
    app.mount("#app")


def action(fn, *args):
    def clicked(event):
        event.preventDefault()
        asyncio.ensure_future(run(fn, *args))

    return clicked


async def run(fn, *args):
    if ctx["busy"]:
        return
    ctx.update(busy=True, message="", error=False)
    try:
        await fn(*args)
    except Exception as exc:
        ctx.update(message=str(exc), error=True)
        if not client.store.getItem("access"):
            ctx["me"] = None
    finally:
        ctx["busy"] = False
        render()


def btn(label, fn, *args, primary=False):
    return t.button(
        label,
        type="button",
        classes="btn btn-primary" if primary else "btn btn-outline-secondary",
        on_click=action(fn, *args),
    )


def field(label, name, options=None, textarea=False, text="", placeholder=""):
    with t.label(classes="field"):
        t.span(label, id=name + "-label")
        if options is not None:
            with t.select(id=name, aria_labelledby=name + "-label", classes="form-select"):
                for key, title in options:
                    t.option(title, value=key, selected=(key == text))
        elif textarea:
            t.textarea(text, id=name, classes="form-control", placeholder=placeholder)
        else:
            t.input(id=name, value=text, classes="form-control", placeholder=placeholder)


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
