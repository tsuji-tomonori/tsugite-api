from urllib.parse import quote, urlencode

import client
import guide_examples as example
from js import window
from portal_labels import ROLE_LABELS
from portal_navigation import load
from portal_ui import btn, ctx, field, value
from puepy import t
from screen_registry import Screen


async def member_add():
    await client.api(
        "/members",
        "POST",
        {
            "email": value("member-email"),
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


def invite_form(projects):
    with t.div(classes="box"):
        t.h2("ユーザーを追加")
        field("メールアドレス", "member-email")
        field("役割", "member-role", options=[("consumer", "利用者"), ("provider", "提供者")])
        field("所属プロジェクト", "member-project", options=[(p, p) for p in projects])
        btn("追加する", member_add, primary=True)


def members_view():
    data = ctx["members"]
    invite_form(data["projects"])
    t.h2("登録ユーザー")
    for row in data["items"]:
        with t.div(classes="compact-row"):
            t.strong(row["username"])
            t.span(ROLE_LABELS.get(row["role"], row["role"]) + "　" + row.get("project", ""))
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
        examples={"member": lambda: invite_form([example.PROJECT["id"]])},
        visible=lambda user: user["admin"],
    ),
)
