# 管理者向けの利用者一覧を取得する。
from __future__ import annotations

from urllib.parse import urlencode

from apis import organization as organization_api
from runtime.portal_ui import ctx


async def load_members(_page: str) -> None:
    """管理者向けの利用者一覧を取得する。"""
    if ctx["me"]["admin"]:
        ctx["members"] = await organization_api.members(
            urlencode({"cursor": ctx.get("member_cursor", "")})
        )
