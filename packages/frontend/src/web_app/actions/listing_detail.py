# 商品の停止・公開範囲・削除を扱う。
from __future__ import annotations

from typing import Any

from apis import products as products_api
from js import document, window
from routing.portal_navigation import go, load
from runtime.portal_ui import ctx, value


async def change_suspension(asset: dict[str, Any]) -> None:
    """商品の利用停止状態を切り替える。"""
    suspended = not asset["suspended"]
    action = "一時停止" if suspended else "再開"
    if window.confirm(asset["name"] + "への全環境のアクセスを" + action + "しますか？"):
        await products_api.suspend(asset["id"], suspended)
        await load()
        ctx["message"] = "APIへのアクセスを" + action + "しました"


async def save_policy(asset: dict[str, Any]) -> None:
    """公開範囲を版番号付きで保存する。"""
    data: dict[str, Any] = {"visibility": value("policy-visibility")}
    for key in ("projects", "departments", "auto_departments", "delegates"):
        fields = document.querySelectorAll('input[name="policy-' + key + '"]:checked')
        data[key] = [str(fields.item(i).value) for i in range(fields.length)]
    data["auto_titles"] = [
        v.strip() for v in value("policy-titles").replace("、", ",").split(",") if v.strip()
    ]
    await products_api.save_policy(asset["id"], asset["revision"], data)
    await load()
    ctx["message"] = "公開範囲と承認ルールを保存しました"


async def delete_listing(asset: dict[str, Any]) -> None:
    """確認済みの商品を削除する。"""
    if window.confirm(asset["name"] + "を削除し、既存の利用権も終了しますか？"):
        await products_api.delete_asset(asset["id"], asset["revision"])
        await go("inventory")
        ctx["message"] = "APIを削除しました"
