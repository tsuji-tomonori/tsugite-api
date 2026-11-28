"""商品の公開・仕様・操作権限のAPIを呼び出す。"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

from apis import client


async def asset(key: str) -> dict[str, Any]:
    """商品詳細を取得する。"""
    return await client.request_object("/apis/" + quote(key, safe=""))


async def catalog(params: dict[str, Any]) -> dict[str, Any]:
    """カタログを検索する。"""
    return await client.request_object("/catalog-page?" + urlencode(params))


async def publication(asset_id: str, published: bool) -> None:
    """商品の公開状態を変更する。"""
    await client.api("/apis/" + asset_id + "/publication?published=" + str(published).lower(), "PUT")


async def operations(asset_id: str) -> dict[str, Any]:
    """操作権限を取得する。"""
    return await client.request_object("/apis/" + asset_id + "/operation-policy")


async def save_operations(asset_id: str, data: dict[str, Any]) -> None:
    """操作権限を保存する。"""
    await client.api("/apis/" + quote(asset_id, safe="") + "/operation-policy", "PUT", data)


async def policy(asset_id: str) -> dict[str, Any]:
    """商品の公開範囲を取得する。"""
    return await client.request_object("/apis/" + asset_id + "/policy")


async def save_policy(asset_id: str, revision: int, data: dict[str, Any]) -> None:
    """商品の公開範囲を保存する。"""
    await client.api("/apis/" + asset_id + "/policy?revision=" + str(revision), "PUT", data)


async def suspend(asset_id: str, suspended: bool) -> None:
    """商品の利用停止状態を保存する。"""
    await client.api("/apis/" + asset_id + "/suspension?suspended=" + str(suspended).lower(), "PUT")


async def delete_asset(asset_id: str, revision: int) -> None:
    """指定した版の商品を削除する。"""
    await client.api("/apis/" + asset_id + "?revision=" + str(revision), "DELETE")


async def update_asset(asset_id: str, revision: int, data: dict[str, Any]) -> dict[str, Any]:
    """指定した版の商品を更新する。"""
    return await client.request_object("/apis/" + asset_id + "?revision=" + str(revision), "PUT", data)


async def create_asset(data: dict[str, Any]) -> dict[str, Any]:
    """商品を登録する。"""
    return await client.request_object("/apis", "POST", data)


async def publication_policy() -> dict[str, Any]:
    """提供ガイドラインと承認順を取得する。"""
    return await client.request_object("/publication-policy")


async def save_publication_policy(data: dict[str, Any]) -> None:
    """これから受け付ける公開申請のルールを保存する。"""
    await client.api("/publication-policy", "PUT", data)


async def publication_requests() -> list[dict[str, Any]]:
    """判断可能な公開申請を取得する。"""
    return await client.request_rows("/publication-requests")


async def decide_publication(key: str, data: dict[str, Any]) -> None:
    """商品版を指定して公開申請を審査する。"""
    await client.api("/apis/" + quote(key, safe="") + "/publication-decisions", "POST", data)
