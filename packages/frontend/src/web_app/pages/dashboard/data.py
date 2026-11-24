# 件数・時系列・直近ログを並行して取得する。
from __future__ import annotations

import asyncio

from apis import activity as activity_api
from runtime.portal_ui import ctx


async def load_dashboard(_page: str) -> None:
    """件数・時系列・直近ログを並行して取得する。"""
    results = await asyncio.gather(
        activity_api.dashboard(),
        activity_api.hourly_metrics(),
        activity_api.recent_logs(),
        return_exceptions=True,
    )
    for key, result in zip(("dashboard", "home_metrics", "recent_logs"), results, strict=True):
        if not isinstance(result, BaseException):
            ctx[key] = result
    for result in results:
        if isinstance(result, BaseException):
            raise result
