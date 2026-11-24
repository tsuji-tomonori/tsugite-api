# 集計の期間と対象を管理する。
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from apis import activity as activity_api
from apis import organization as organization_api
from runtime.portal_ui import ctx


def time_params() -> dict[str, Any]:
    """絞り込み条件からUTCの集計期間を作る。"""
    f = ctx["filters"]
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=int(f["hours"]))
    return {
        k: v
        for k, v in {
            "start": f["start"] or start.isoformat(),
            "end": f["end"] or end.isoformat(),
            "unit": f["unit"],
            "asset_id": f["asset"],
            "project": f["project"],
            "environment": f["env"],
            "status": f["status"],
        }.items()
        if v
    }


async def load_dimensions(scope: str = "metrics") -> None:
    """閲覧範囲に合わせて集計軸の候補を取得する。"""
    ctx["workspace"] = await organization_api.workspace()
    allowed = ctx["workspace"]["leads"]
    if scope == "audit" and ctx["me"].get("auditor"):
        allowed = [u["id"] for u in ctx["workspace"]["units"]]
    if scope == "personal" or ctx["filters"]["unit"] not in allowed:
        ctx["filters"]["unit"] = ""
    params = {"unit": ctx["filters"]["unit"]}
    path = "/metric-dimensions"
    if scope != "metrics":
        path = "/access-logs/dimensions"
        params["scope"] = scope
    ctx["dims"] = await activity_api.dimensions(path, params)
