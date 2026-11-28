"""利用者の一覧と招待フォームを表示する。"""

from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import quote

from actions.members import change_admin_role, member_add, member_page, member_remove
from puepy import t
from routing.portal_navigation import go
from runtime.portal_ui import action, ctx

from components.controls import btn, field
from components.list_layout import disclosure, result_table
from components.member_identity import full_name_cell


def invite_form(projects: Sequence[str], *, expanded: bool = False) -> None:
    """利用者の招待フォームを描画する。"""
    with disclosure("ユーザーを追加", expanded=expanded), t.form(on_submit=action(member_add)):
        field("ユーザー名（メールアドレス）", "member-email", required=True)
        field("氏名", "member-full-name", required=True)
        field("表示名", "member-display-name", required=False)
        field("所属プロジェクト", "member-project", options=[(p, p) for p in projects])
        t.button("追加する", type="submit", classes="btn btn-primary")


def members_view() -> None:
    """利用者の一覧と管理操作を描画する。"""
    data = ctx["members"]
    with t.div(classes="list-tools"):
        invite_form(data["projects"])
    with result_table(
        "登録ユーザー",
        ("ユーザー名", "氏名", "メールアドレス", "所属プロジェクト", "管理者権限", "操作"),
    ):
        for row in data["items"]:
            with t.tr():
                t.th(row["username"], scope="row")
                full_name_cell(row)
                t.td(row.get("email") or "—")
                t.td(row.get("project") or "—")
                t.td("あり" if row.get("admin") else "なし")
                with t.td(), t.div(classes="btn-grouping"):
                    if not row.get("deleted"):
                        btn(
                            "管理者権限を剥奪" if row.get("admin") else "管理者権限を付与",
                            change_admin_role,
                            row,
                        )
                        btn("プロフィールを編集", go, "member-profile/" + quote(row["subject"], safe=""))
                    if row["subject"] != ctx["me"]["subject"]:
                        btn("削除", member_remove, row)
    if data["next"]:
        btn("次のユーザー", member_page, data["next"])
    if ctx.get("member_cursor"):
        btn("先頭に戻る", member_page, "")
