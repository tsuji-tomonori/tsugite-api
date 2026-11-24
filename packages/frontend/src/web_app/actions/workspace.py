# 部署とプロジェクトの画面状態を扱う。
from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from apis import organization as organization_api
from components import workspace_views as directory
from js import window
from routing.portal_navigation import load
from runtime.portal_ui import ctx, route

KINDS = {"departments": ("department", "部署"), "projects": ("project", "プロジェクト")}


def location() -> tuple[str, list[str]]:
    """現在のURLから対象の種類と操作を取り出す。"""
    root, *parts = route().split("/")
    if root == "attributes" and parts:
        return "attributes/" + parts[0], [unquote(part) for part in parts[1:]]
    return ("departments" if root == "workspace" else root), [unquote(part) for part in parts]


def kind_label(root: str) -> tuple[str, str]:
    """登録済みの項目から種類と表示名を解決する。"""
    if root in KINDS:
        return KINDS[root]
    key = root.partition("/")[2]
    fields = (ctx.get("workspace") or {}).get("metadata_fields", [])
    return key, next((f["label"] for f in fields if f["key"] == key and not f["builtin"]), "")


def attribute_menu(user: dict[str, Any]) -> list[tuple[str, str]]:
    """任意項目に対応するメニューを作る。"""
    return [
        ("attributes/" + f["key"], f["label"])
        for f in user.get("metadata_fields", [])
        if not f["builtin"]
    ]


async def load_workspace(page: str) -> None:
    """閲覧できる組織情報と集計を読み込む。"""
    for key in ("workspace", "workspace_usage", "member_form"):
        ctx.pop(key, None)
    data = await organization_api.workspace()
    if page != route():
        return
    ctx["workspace"] = data
    root, parts = location()
    if root in KINDS and len(parts) == 2 and parts[0] == "monitor":
        unit = next(
            (u for u in data["units"] if u["id"] == parts[1] and u["kind"] == KINDS[root][0]), None
        )
        if unit and (data["admin"] or unit["id"] in data["leads"]):
            usage = await organization_api.unit_usage(directory.endpoint(unit))
            if page == route():
                ctx["workspace_usage"] = usage


async def toggle(unit: dict[str, Any]) -> None:
    """選択した組織の利用停止状態を切り替える。"""
    stopped = not unit["stopped"]
    verb = "停止" if stopped else "再開"
    if window.confirm(unit["name"] + " のAPI利用を" + verb + "しますか？"):
        await organization_api.unit_state(directory.endpoint(unit), {"stopped": stopped})
        await load()
        ctx["message"] = "API利用を" + verb + "しました"
