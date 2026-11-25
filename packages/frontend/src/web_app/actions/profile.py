# 利用者プロフィールの読み書きを扱う。
from __future__ import annotations

import asyncio

from apis import organization as organization_api
from runtime.portal_ui import ctx, route, value


def profile_endpoint(page: str) -> str:
    """表示対象に対応するAPIパスを選ぶ。"""
    if page == "profile":
        return "/me/profile"
    return "/members/" + page.partition("/")[2] + "/profile"


async def load_profile(page: str) -> None:
    """対象者のプロフィールを取得する。"""
    if page == "profile" or ctx["me"]["admin"]:
        profile, directory = await asyncio.gather(
            organization_api.profile(profile_endpoint(page)), organization_api.workspace()
        )
        if page == route():
            ctx.update(member_profile=profile, profile_directory=directory)


async def save(endpoint: str, revision: int) -> None:
    """変更したプロフィールを保存する。"""
    ctx["member_profile"] = await organization_api.update_profile(
        endpoint,
        {
            "revision": revision,
            "full_name": value("profile-full-name") or None,
            "display_name": value("profile-display-name") or None,
        },
    )
    ctx["message"] = "プロフィールを保存しました"
