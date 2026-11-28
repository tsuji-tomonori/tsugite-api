# 部署・プロジェクト・利用者のAPIを呼び出す。
from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

from apis import client


async def workspace() -> dict[str, Any]:
    """所属と組織の一覧を取得する。"""
    return await client.request_object("/workspace")


async def members(query: str) -> dict[str, Any]:
    """条件に合う利用者一覧を取得する。"""
    return await client.request_object("/members?" + query)


async def add_member(data: dict[str, Any]) -> dict[str, Any]:
    """利用者を追加する。"""
    return await client.request_object("/members", "POST", data)


async def remove_member(subject: str, username: str) -> None:
    """対象者のログインを停止する。"""
    await client.api(
        "/members/" + quote(subject, safe="") + "?" + urlencode({"username": username}), "DELETE"
    )


async def membership(data: dict[str, Any]) -> None:
    """所属を保存する。"""
    await client.api("/workspace/memberships", "PUT", data)


async def remove_membership(query: str) -> None:
    """所属を解除する。"""
    await client.api("/workspace/memberships?" + query, "DELETE")


async def save_unit(key: str, data: dict[str, Any]) -> None:
    """部署またはプロジェクトを保存する。"""
    await client.api("/workspace/units/" + quote(key, safe=""), "PUT", data)


async def delete_unit(endpoint: str) -> None:
    """対象の組織を削除する。"""
    await client.api(endpoint, "DELETE")


async def transfer_unit(endpoint: str, data: dict[str, Any]) -> None:
    """組織の管理対象を移管する。"""
    await client.api(endpoint + "/transfer", "POST", data)


async def unit_usage(endpoint: str) -> dict[str, Any]:
    """組織単位の利用実績を取得する。"""
    return await client.request_object(endpoint + "/usage")


async def unit_state(endpoint: str, data: dict[str, Any]) -> None:
    """組織の利用停止状態を保存する。"""
    await client.api(endpoint + "/state", "PUT", data)


async def profile(endpoint: str) -> dict[str, Any]:
    """対象者のプロフィールを取得する。"""
    return await client.request_object(endpoint)


async def update_profile(endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
    """対象者のプロフィールを更新する。"""
    return await client.request_object(endpoint, "PATCH", data)


async def save_field(key: str, data: dict[str, Any]) -> None:
    """メタデータ項目の設定を保存する。"""
    await client.api("/workspace/metadata/" + quote(key, safe=""), "PUT", data)


async def set_admin_role(subject: str, admin: bool) -> None:
    """利用者の管理者権限を設定する。"""
    await client.api("/members/" + quote(subject, safe="") + "/admin-role", "PUT", {"admin": admin})
