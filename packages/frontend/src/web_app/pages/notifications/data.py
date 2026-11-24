# 通知先と受信一覧を読み込む。
from __future__ import annotations

from actions.management_targets import load_targets
from apis import messages as messages_api
from runtime.portal_ui import ctx


async def load_notifications(_page: str) -> None:
    """通知先と受信一覧を読み込む。"""
    await load_targets()
    ctx["notices"] = await messages_api.notices(ctx.get("notice_offset", 0))
