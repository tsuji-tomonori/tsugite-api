# 通知の配信と既読状態を扱う。
from __future__ import annotations

from apis import messages as messages_api
from routing.portal_navigation import load
from runtime.portal_ui import ctx, value


async def send_notice() -> None:
    """選択した対象に通知を送る。"""
    if ctx["me"]["admin"]:
        project, asset = value("notify-project"), ""
    else:
        asset, project, _ = value("notify-target").split("/")
    await messages_api.notice(
        {
            "title": value("notify-title"),
            "body": value("notify-body"),
            "asset_id": asset,
            "project": project,
        }
    )
    await load()
    ctx["message"] = "通知を送信しました"


async def read_notice(key: str) -> None:
    """通知を既読にする。"""
    await messages_api.read(key)
    await load()


async def more_notices(offset: int) -> None:
    """次の通知を表示する。"""
    ctx["notice_offset"] = offset
    await load()
