"""設定可能な対象と現在のルールを読み込む。"""

from __future__ import annotations

from actions.management_targets import load_targets
from apis import activity as activity_api
from runtime.portal_ui import ctx


async def load_alerts(_page: str) -> None:
    """設定可能な対象と現在のルールを読み込む。"""
    await load_targets()
    ctx["rules"] = await activity_api.alerts()
