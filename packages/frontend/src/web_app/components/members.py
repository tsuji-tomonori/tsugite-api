# 利用者の一覧と招待フォームを表示する。
from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import quote

from actions.members import change_admin_role, member_add, member_page, member_remove
from content.portal_labels import ROLE_LABELS
from puepy import t
from routing.portal_navigation import go
from runtime.portal_ui import ctx

from components.controls import btn, field
from components.list_layout import disclosure, result_table


def invite_form(projects: Sequence[str], *, expanded: bool = False) -> None:
    """利用者の招待フォームを描画する。"""
    with disclosure("ユーザーを追加", expanded=expanded):
        field("メールアドレス", "member-email")
        field("氏名", "member-full-name", required=False)
        field("表示名", "member-display-name", required=False)
        field("役割", "member-role", options=[("consumer", "利用者"), ("provider", "提供者")])
        field("所属プロジェクト", "member-project", options=[(p, p) for p in projects])
        btn("追加する", member_add, primary=True)


def members_view() -> None:
    """利用者の一覧と管理操作を描画する。"""
    data = ctx["members"]
    with t.div(classes="list-tools"):
        invite_form(data["projects"])
    with result_table(
        "登録ユーザー", ("名前", "メールアドレス", "役割", "所属プロジェクト", "管理者権限", "操作")
    ):
        for row in data["items"]:
            with t.tr():
                with t.th(scope="row"):
                    t.span(row.get("display_name") or row.get("full_name") or row["username"])
                    if row.get("display_name") and row.get("full_name") not in (
                        None,
                        row["display_name"],
                    ):
                        t.div(row["full_name"])
                t.td(row.get("email") or "—")
                t.td(ROLE_LABELS.get(row["role"], row["role"]))
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
