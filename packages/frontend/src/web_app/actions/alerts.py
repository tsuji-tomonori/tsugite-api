# 利用件数ルールを管理する。
from __future__ import annotations

from apis import activity as activity_api
from routing.portal_navigation import load
from runtime.portal_ui import ctx, value


async def save_alert() -> None:
    """入力した利用件数ルールを保存する。"""
    asset, project, env = value("alert-target").split("/")
    await activity_api.save_alert(
        {
            "asset_id": asset,
            "project": project,
            "environment": env,
            "threshold": int(value("alert-threshold")),
            "minutes": int(value("alert-minutes")),
            "stop": value("alert-action") == "stop",
            "enabled": value("alert-action") != "off",
        }
    )
    await load()
    ctx["message"] = "アラート設定を保存しました"
