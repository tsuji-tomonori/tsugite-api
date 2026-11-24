# ユーザー管理の操作を扱う。
from __future__ import annotations

from typing import Any

from apis import organization as organization_api
from js import window
from routing.portal_navigation import load
from runtime.portal_ui import ctx, value


async def member_add() -> None:
    """フォームの利用者を招待する。"""
    await organization_api.add_member(
        {
            "email": value("member-email"),
            "full_name": value("member-full-name") or None,
            "display_name": value("member-display-name") or None,
            "role": value("member-role"),
            "project": value("member-project"),
        }
    )
    await load()
    ctx["message"] = "ユーザーを追加しました"


async def member_remove(row: dict[str, Any]) -> None:
    """確認済みの利用者を削除する。"""
    if not window.confirm(row["username"] + " を削除してログインを停止しますか？"):
        return
    await organization_api.remove_member(row["subject"], row["username"])
    ctx["member_cursor"] = ""
    await load()


async def member_page(cursor: str) -> None:
    """カーソルの位置に移動する。"""
    ctx["member_cursor"] = cursor
    await load()
