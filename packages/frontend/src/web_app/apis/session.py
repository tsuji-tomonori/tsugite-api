# ポータルの起動とセッションのAPIを呼び出す。
from __future__ import annotations

from typing import Any

from apis import client


async def config() -> dict[str, Any]:
    """起動設定を取得する。"""
    return await client.request_object("/config")


async def me() -> dict[str, Any]:
    """ログイン中の利用者を取得する。"""
    return await client.request_object("/me")


async def demo(persona: str) -> dict[str, Any]:
    """デモ利用者としてログインする。"""
    return await client.request_object("/demo/" + persona, "POST")
