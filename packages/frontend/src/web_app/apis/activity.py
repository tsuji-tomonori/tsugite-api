# 監視・監査・アクセスログのAPIを呼び出す。
from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from apis import client
from apis.invocation import fetch


async def dimensions(path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """集計条件の候補を取得する。"""
    return await client.request_rows(path + "?" + urlencode(params))


async def dashboard() -> dict[str, Any]:
    """ダッシュボードの件数を取得する。"""
    return await client.request_object("/dashboard")


async def hourly_metrics() -> dict[str, Any]:
    """一時間区切りの集計を取得する。"""
    return await client.request_object("/metrics?minutes=60")


async def recent_logs() -> list[dict[str, Any]]:
    """直近のアクセスログを取得する。"""
    return await client.request_rows("/access-logs")


async def logs(params: dict[str, Any]) -> list[dict[str, Any]]:
    """条件に合うログを取得する。"""
    return await client.request_rows("/access-logs?" + urlencode(params))


async def log_detail(request_id: str, unit: str, scope: str) -> dict[str, Any]:
    """閲覧範囲内のログ一件を取得する。"""
    return await client.request_object(
        "/access-logs/detail?" + urlencode({"request_id": request_id, "unit": unit, "scope": scope})
    )


async def audit(params: dict[str, Any]) -> list[dict[str, Any]]:
    """条件に合う業務操作履歴を取得する。"""
    return await client.request_rows("/audit?" + urlencode(params))


async def metrics(params: dict[str, Any]) -> dict[str, Any]:
    """指定期間のメトリクスを取得する。"""
    return await client.request_object("/metrics?" + urlencode(params))


async def targets() -> list[dict[str, Any]]:
    """管理できる利用対象を取得する。"""
    return await client.request_rows("/management-targets")


async def alerts() -> list[dict[str, Any]]:
    """アラート設定を取得する。"""
    return await client.request_rows("/alerts")


async def save_alert(data: dict[str, Any]) -> None:
    """アラート設定を保存する。"""
    await client.api("/alerts", "PUT", data)


async def download_chunk(params: dict[str, Any]) -> Any:
    """アクセスログの次の区間を認証付きで取得する。"""
    return await fetch(
        client.prefix + "/access-logs/download?" + urlencode(params),
        headers={
            **client.screen_headers(),
            "Authorization": "Bearer " + str(client.store.getItem("access")),
        },
    )
