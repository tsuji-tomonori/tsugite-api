# 利用者の一覧と招待フォームを表示する。
from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import quote

from actions.members import member_add, member_page, member_remove
from content.portal_labels import ROLE_LABELS
from puepy import t
from routing.portal_navigation import go
from runtime.portal_ui import ctx

from components.controls import btn, field


def invite_form(projects: Sequence[str]) -> None:
    """利用者の招待フォームを描画する。"""
    with t.div(classes="box"):
        t.h2("ユーザーを追加")
        field("メールアドレス", "member-email")
        field("氏名", "member-full-name", required=False)
        field("表示名", "member-display-name", required=False)
        field("役割", "member-role", options=[("consumer", "利用者"), ("provider", "提供者")])
        field("所属プロジェクト", "member-project", options=[(p, p) for p in projects])
        btn("追加する", member_add, primary=True)


def members_view() -> None:
    """利用者の一覧と管理操作を描画する。"""
    data = ctx["members"]
    invite_form(data["projects"])
    t.h2("登録ユーザー")
    for row in data["items"]:
        with t.div(classes="compact-row"):
            t.strong(row.get("display_name") or row.get("full_name") or row["username"])
            if row.get("display_name") and row.get("full_name") not in (None, row["display_name"]):
                t.span(row["full_name"])
            if row.get("email"):
                t.span(row["email"])
            t.span(ROLE_LABELS.get(row["role"], row["role"]) + "　" + row.get("project", ""))
            if not row.get("deleted"):
                btn("プロフィールを編集", go, "member-profile/" + quote(row["subject"], safe=""))
            if row["subject"] != ctx["me"]["subject"]:
                btn("削除", member_remove, row)
    if data["next"]:
        btn("次のユーザー", member_page, data["next"])
    if ctx.get("member_cursor"):
        btn("先頭に戻る", member_page, "")
