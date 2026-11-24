# 利用者プロフィールの編集欄を表示する。
from __future__ import annotations

from actions.profile import load_profile, profile_endpoint, save
from puepy import t
from routing.portal_navigation import go
from runtime.portal_ui import ctx, route

from components.controls import btn, field


def view() -> None:
    """本人または管理対象者のプロフィールを表示する。"""
    page = route()
    if page != "profile" and not ctx["me"]["admin"]:
        t.p("プロフィールの管理には管理者の権限が必要です。")
        return
    profile = ctx.get("member_profile")
    if profile is None:
        return
    with t.section(classes="box"):
        t.p("メールアドレス　" + (profile["email"] or "—"))
        field("氏名", "profile-full-name", text=profile["full_name"] or "", required=False)
        field("表示名", "profile-display-name", text=profile["display_name"] or "", required=False)
        with t.div(classes="btn-grouping"):
            btn("保存する", save, profile_endpoint(page), profile["revision"], primary=True)
            btn("再読み込み", load_profile, page)
            if page != "profile":
                btn("ユーザー管理に戻る", go, "members")
