import asyncio
from urllib.parse import quote

import api_docs
import client
import manual_request
from openapi_fields import parameters, resolve
from portal_ui import action, ctx, value
from puepy import t
from screen_registry import Screen


async def load_console(page):
    ctx.update(console_asset=None, console_operation="", console_rights=[], console_keys=[])
    rights, keys = await asyncio.gather(client.api("/requests"), client.api("/keys"))
    ctx["console_rights"] = [r for r in rights if r["status"] == "approved"]
    ctx["console_keys"] = [k for k in keys if k.get("mode") in ("app", "bearer")]
    if key := page.partition("/")[2]:
        await open_asset(key)


async def select_asset():
    await open_asset(value("console-asset"))


async def open_asset(key):
    ctx.update(console_asset=None, console_operation="")
    if key and any(r["asset_id"] == key for r in ctx["console_rights"]):
        ctx["console_asset"] = await client.api("/apis/" + quote(key, safe=""))


async def select_operation():
    ctx["console_operation"] = value("console-operation")


def select(label, identifier, choices, selected, change):
    with t.label(classes="field"):
        t.span(label)
        with t.select(id=identifier, classes="form-select", aria_label=label, on_change=action(change)):
            for key, title in choices:
                t.option(title, value=key, selected=key == selected)


def operations(asset):
    spec = asset["spec"]
    allowed = asset.get("allowed_operations")
    result = {}
    for path, raw in spec["paths"].items():
        item = resolve(spec, raw)
        if not isinstance(item, dict):
            continue
        for method in api_docs.METHODS:
            name = method.upper() + " " + path
            if method not in api_docs.INVOKABLE or allowed is not None and name not in allowed:
                continue
            op = item.get(method)
            if isinstance(op, dict):
                result[name] = method, path, op, parameters(spec, item, op)
    return result


def bindings(asset, name):
    rights = [
        r
        for r in ctx["console_rights"]
        if r["asset_id"] == asset["id"] and r["environment"] in asset["environments"]
    ]
    result = []
    for entry in api_docs.available_bindings(
        asset["id"], rights, ctx["console_keys"], ctx["me"]["subject"]
    ):
        allowed = entry[0].get("operations", {}).get(asset["id"])
        if allowed is None or name in allowed:
            result.append(entry)
    return result


def approved_view():
    t.h2("承認済みAPIから選ぶ")
    assets = {r["asset_id"]: r["asset_name"] for r in ctx.get("console_rights", [])}
    if not assets:
        t.p("利用が承認されたAPIはありません。")
        t.a("利用申請の状況を確認", href="#/mine")
        return
    asset = ctx.get("console_asset")
    select(
        "API商品",
        "console-asset",
        [("", "選んでください"), *assets.items()],
        asset["id"] if asset else "",
        select_asset,
    )
    if not asset:
        return
    if asset["suspended"]:
        t.p("このAPIは一時停止中です。")
        return
    choices = operations(asset)
    if not choices:
        t.p("このAPIで実行できる操作はありません。")
        return
    name = ctx.get("console_operation") or next(iter(choices))
    select(
        "OpenAPIの操作",
        "console-operation",
        [(n, (n + "　" + o.get("summary", "")).strip()) for n, (_, _, o, _) in choices.items()],
        name,
        select_operation,
    )
    method, path, op, params = choices[name]
    options = bindings(asset, name)
    if not options:
        t.p("この操作を実行できる認証情報がありません。")
        t.a("認証情報を作成・管理する", href="#/keys")
        return
    if op.get("description"):
        t.p(op["description"])
    body = resolve(asset["spec"], op.get("requestBody", {}))
    api_docs.try_operation(
        asset["spec"],
        asset,
        options,
        method,
        path,
        params,
        body,
        "console-call",
        binding_label="認証情報・プロジェクト・環境（必須）",
        submit_label="この操作を実行",
    )


def console_view():
    with t.section(classes="box"):
        approved_view()
    manual_request.view()


SCREENS = (
    Screen("console", "APIクライアント", console_view, load_console, group="ワークスペース", order=25),
    Screen("console/", "APIクライアント", console_view, load_console, parent="console"),
)
