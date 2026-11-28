"""指定期間の時系列を取得する。"""

from __future__ import annotations

from actions.activity import load_dimensions, time_params
from apis import activity as activity_api
from runtime.portal_ui import ctx


async def load_metrics(_page: str) -> None:
    """指定期間の時系列を取得する。"""
    await load_dimensions()
    params = time_params()
    ctx["metrics"] = await activity_api.metrics({**params, "minutes": ctx["filters"]["minutes"]})
