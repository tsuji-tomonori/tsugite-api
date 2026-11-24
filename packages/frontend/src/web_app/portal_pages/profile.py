# 本人と全体管理者が利用者プロフィールを変更する画面。
"""本人と全体管理者が利用者プロフィールを変更する画面。"""

import client
from portal_navigation import go
from portal_ui import btn, ctx, field, route, value
from puepy import t
from screen_registry import Screen


def profile_endpoint(page):
    if page == "profile":
        return "/me/profile"
    return "/members/" + page.partition("/")[2] + "/profile"


async def load_profile(page):
    if page == "profile" or ctx["me"]["admin"]:
        ctx["member_profile"] = await client.api(profile_endpoint(page))


async def save(endpoint, revision):
    ctx["member_profile"] = await client.api(
        endpoint,
        "PATCH",
        {
            "revision": revision,
            "full_name": value("profile-full-name") or None,
            "display_name": value("profile-display-name") or None,
        },
    )
    ctx["message"] = "プロフィールを保存しました"


def view():
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


SCREENS = (
    Screen(
        "profile",
        "自分のプロフィール",
        view,
        load_profile,
        group="個人設定",
        order=105,
        clear_on_load=("member_profile",),
    ),
    Screen(
        "member-profile/",
        "利用者のプロフィール",
        view,
        load_profile,
        parent="members",
        clear_on_load=("member_profile",),
    ),
)
