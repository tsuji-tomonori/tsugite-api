# 承認済みAPIと手動リクエストの操作欄を表示する。
from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from actions.console import select_asset, select_operation
from content.openapi_fields import parameters, resolve
from puepy import t
from runtime.portal_ui import action, ctx

from components import api_docs, manual_request


def select(
    label: str,
    identifier: str,
    choices: Sequence[tuple[str, str]],
    selected: str,
    change: Callable[..., Awaitable[None]],
) -> None:
    """変更時の処理を持つ選択欄を描画する。"""
    with t.label(classes="field"):
        t.span(label)
        with t.select(id=identifier, classes="form-select", aria_label=label, on_change=action(change)):
            for key, title in choices:
                t.option(title, value=key, selected=key == selected)


def operations(
    asset: dict[str, Any],
) -> dict[str, tuple[str, str, dict[str, Any], list[dict[str, Any]]]]:
    """呼び出しを許可された操作を列挙する。"""
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


def bindings(asset: dict[str, Any], name: str) -> list[tuple[dict[str, Any], str, str, str]]:
    """操作に使える認証情報を抽出する。"""
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


def approved_view() -> None:
    """承認済み商品から実行操作を選ぶ欄を表示する。"""
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


def console_view() -> None:
    """承認済みAPIと手動実行の欄を組み立てる。"""
    with t.section(classes="box"):
        approved_view()
    manual_request.view()
