# ユーザー管理の画面と操作を定義する。
from urllib.parse import quote, urlencode

import client
import guide_examples as example
from js import window
from list_layout import disclosure, result_table
from portal_labels import ROLE_LABELS
from portal_navigation import go, load
from portal_ui import btn, ctx, field, value
from puepy import t
from screen_registry import Screen


async def member_add():
    await client.api(
        "/members",
        "POST",
        {
            "email": value("member-email"),
            "full_name": value("member-full-name") or None,
            "display_name": value("member-display-name") or None,
            "role": value("member-role"),
            "project": value("member-project"),
        },
    )
    await load()
    ctx["message"] = "ユーザーを追加しました"


async def member_remove(row):
    if not window.confirm(row["username"] + " を削除してログインを停止しますか？"):
        return
    await client.api(
        "/members/" + quote(row["subject"], safe="") + "?" + urlencode({"username": row["username"]}),
        "DELETE",
    )
    ctx["member_cursor"] = ""
    await load()


async def member_page(cursor):
    ctx["member_cursor"] = cursor
    await load()


def invite_form(projects, *, expanded=False):
    with disclosure("ユーザーを追加", expanded=expanded):
        field("メールアドレス", "member-email")
        field("氏名", "member-full-name", required=False)
        field("表示名", "member-display-name", required=False)
        field("役割", "member-role", options=[("consumer", "利用者"), ("provider", "提供者")])
        field("所属プロジェクト", "member-project", options=[(p, p) for p in projects])
        btn("追加する", member_add, primary=True)


def members_view():
    data = ctx["members"]
    with t.div(classes="list-tools"):
        invite_form(data["projects"])
    with result_table("登録ユーザー", ("名前", "メールアドレス", "役割", "所属プロジェクト", "操作")):
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
                with t.td(), t.div(classes="btn-grouping"):
                    if not row.get("deleted"):
                        btn("プロフィールを編集", go, "member-profile/" + quote(row["subject"], safe=""))
                    if row["subject"] != ctx["me"]["subject"]:
                        btn("削除", member_remove, row)
    if data["next"]:
        btn("次のユーザー", member_page, data["next"])
    if ctx.get("member_cursor"):
        btn("先頭に戻る", member_page, "")


async def load_members(_page):
    if ctx["me"]["admin"]:
        ctx["members"] = await client.api(
            "/members?" + urlencode({"cursor": ctx.get("member_cursor", "")})
        )


def view():
    if ctx["me"]["admin"]:
        members_view()


SCREENS = (
    Screen(
        "members",
        "ユーザー管理",
        view,
        load_members,
        group="管理",
        order=100,
        examples={"member": lambda: invite_form([example.PROJECT["id"]], expanded=True)},
        visible=lambda user: user["admin"],
    ),
)
