# ユーザー管理の操作を扱う。
from __future__ import annotations

from typing import Any

from apis import client
from apis import organization as organization_api
from js import window
from routing.portal_navigation import go, load
from runtime.portal_ui import ctx, value


async def member_add() -> None:
    """フォームの利用者を招待する。"""
    username = value("member-email")
    if not username:
        raise client.InputError("ユーザー名（メールアドレス）を入力してください")
    full_name = value("member-full-name")
    if not full_name:
        raise client.InputError("氏名を入力してください")
    await organization_api.add_member(
        {
            "email": username,
            "full_name": full_name,
            "display_name": value("member-display-name") or None,
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


async def change_admin_role(row: dict[str, Any]) -> None:
    """対象者と操作を確認して管理者権限を更新する。"""
    grant = not row.get("admin")
    action = "付与" if grant else "剥奪"
    if not window.confirm(f"{row['username']} の管理者権限を{action}しますか？"):
        return
    await organization_api.set_admin_role(row["subject"], grant)
    if not grant and row["subject"] == ctx["me"]["subject"]:
        await go("catalog")
    else:
        await load()
    ctx["message"] = f"管理者権限を{action}しました"
