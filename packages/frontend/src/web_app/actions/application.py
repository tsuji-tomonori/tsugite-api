"""利用申請の入力と送信を扱う。"""

from __future__ import annotations

from typing import Any

from apis import access as access_api
from apis import client
from components import product_views
from routing.portal_navigation import go
from runtime.portal_ui import ctx, value


async def apply(asset: dict[str, Any]) -> None:
    """フォームの回答を添えて利用を申請する。"""
    if not value("reason"):
        raise client.InputError("利用目的を入力してください")
    await access_api.apply(
        asset["id"],
        {
            "project": value("project"),
            "personal": value("grant-kind") == "personal"
            or value("project") == ctx["me"]["personal_project"],
            "environment": value("environment"),
            "reason": value("reason"),
            **product_views.answers(asset, value("environment"), value),
        },
    )
    await go("mine")
    ctx["message"] = "利用申請を送信しました"
