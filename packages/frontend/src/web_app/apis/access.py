"""利用申請と認証情報のAPIを呼び出す。"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

from apis import client


async def requests() -> list[dict[str, Any]]:
    """自分の利用申請を取得する。"""
    return await client.request_rows("/requests")


async def asset_requests(asset_id: str) -> list[dict[str, Any]]:
    """商品に対する利用申請を取得する。"""
    return await client.request_rows("/requests?" + urlencode({"asset_id": asset_id}))


async def apply(asset_id: str, data: dict[str, Any]) -> None:
    """利用申請を提出する。"""
    await client.api("/apis/" + asset_id + "/requests", "POST", data)


async def review(key: str, data: dict[str, Any]) -> None:
    """申請の判断結果を送信する。"""
    await client.api("/requests/" + key, "POST", data)


async def request_list(incoming: bool) -> list[dict[str, Any]]:
    """提出または受信した申請を取得する。"""
    return await client.request_rows("/requests?incoming=" + str(incoming).lower())


async def keys() -> list[dict[str, Any]]:
    """利用可能なキーを取得する。"""
    return await client.request_rows("/keys")


async def key_assets() -> list[dict[str, Any]]:
    """キーに指定できる商品を取得する。"""
    return await client.request_rows("/key-assets")


async def create_key(data: dict[str, Any]) -> dict[str, Any]:
    """キーを作成する。"""
    return await client.request_object("/keys", "POST", data)


async def delete_key(key: str) -> None:
    """キーを削除する。"""
    await client.api("/keys/" + quote(key, safe=""), "DELETE")


async def issue(data: dict[str, Any]) -> dict[str, Any]:
    """認証情報を発行する。"""
    return await client.request_object("/credentials", "POST", data)


async def options(project: str) -> dict[str, Any]:
    """発行条件の候補を取得する。"""
    return await client.request_object("/credentials/options?" + urlencode({"project": project}))


async def token(key: str) -> dict[str, Any]:
    """アクセストークンを取得する。"""
    return await client.request_object("/credentials/" + quote(key, safe="") + "/token", "POST")


async def rotate(key: str) -> dict[str, Any]:
    """認証情報を更新する。"""
    return await client.request_object("/credentials/" + quote(key, safe="") + "/rotate", "POST")


async def limits(endpoint: str) -> dict[str, Any]:
    """有効期限の上限を取得する。"""
    return await client.request_object(endpoint)


async def save_limits(endpoint: str, data: dict[str, Any]) -> None:
    """有効期限の上限を保存する。"""
    await client.api(endpoint, "PUT", data)
