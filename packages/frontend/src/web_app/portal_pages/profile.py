"""本人と全体管理者が利用者プロフィールを変更する画面。"""

import asyncio
from urllib.parse import unquote

import client
from portal_navigation import go
from portal_ui import btn, ctx, field, route, value
from puepy import t
from screen_registry import Screen
from workspace_views import unit_paths


def profile_endpoint(page):
    if page == "profile":
        return "/me/profile"
    return "/members/" + page.partition("/")[2] + "/profile"


async def load_profile(page):
    if page == "profile" or ctx["me"]["admin"]:
        profile, directory = await asyncio.gather(
            client.api(profile_endpoint(page)), client.api("/workspace")
        )
        if page == route():
            ctx.update(member_profile=profile, profile_directory=directory)


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

    directory = ctx.get("profile_directory")
    if directory:
        subject = ctx["me"]["subject"] if page == "profile" else unquote(page.partition("/")[2])
        person_metadata(directory, subject)


def person_metadata(directory, subject):
    units = {unit["id"]: unit for unit in directory["units"]}
    paths = unit_paths(units)
    rows = {r["unit_id"]: r for r in directory["memberships"] if r["subject"] == subject}
    if subject == ctx["me"]["subject"]:
        for key in directory["my_units"]:
            rows.setdefault(key, {})
    with t.section(classes="box"):
        t.h2("利用者のメタデータ")
        with t.div(classes="resource-table"), t.table(aria_label="利用者のメタデータ"):
            with t.thead(), t.tr():
                for label in ("項目", "設定されている値", "グループ内の役割"):
                    t.th(label, scope="col")
            with t.tbody():
                for item in directory["metadata_fields"]:
                    for key in sorted(rows, key=lambda k: paths.get(k, k)):
                        if units.get(key, {}).get("kind") != item["key"]:
                            continue
                        with t.tr():
                            t.th(item["label"], scope="row")
                            t.td(paths[key])
                            row = rows[key]
                            t.td(
                                " / ".join(
                                    filter(
                                        None, ["リーダー" if row.get("leader") else "", row.get("title")]
                                    )
                                )
                                or "—"
                            )
        if not rows:
            t.p("設定されている値はありません。")


SCREENS = (
    Screen(
        "profile",
        "自分のプロフィール",
        view,
        load_profile,
        group="個人設定",
        order=105,
        clear_on_load=("member_profile", "profile_directory"),
    ),
    Screen(
        "member-profile/",
        "利用者のプロフィール",
        view,
        load_profile,
        parent="members",
        clear_on_load=("member_profile", "profile_directory"),
    ),
)
