# 利用申請の画面と操作を定義する。
from urllib.parse import quote

import client
import guide_examples as example
import product_views
from portal_navigation import go
from portal_ui import btn, ctx, field, value
from puepy import t
from screen_registry import Screen


async def load_application(page):
    ctx["detail"] = None
    ctx["detail"] = await client.api("/apis/" + quote(page.split("/", 1)[1], safe=""))


async def apply(asset):
    if not value("reason"):
        raise client.InputError("利用目的を入力してください")
    await client.api(
        "/apis/" + asset["id"] + "/requests",
        "POST",
        {
            "project": value("project"),
            "personal": value("grant-kind") == "personal"
            or value("project") == ctx["me"]["personal_project"],
            "environment": value("environment"),
            "reason": value("reason"),
            **product_views.answers(asset, value("environment"), value),
        },
    )
    await go("mine")
    ctx["message"] = "利用申請を送信しました"


def application_page():
    a = ctx["detail"]
    t.h1("利用申請")
    if not a:
        t.p("APIを読み込み中…")
        return
    t.p(a["name"])
    t.a("APIの詳細に戻る", href="#/api/" + a["id"])
    if not a["published"]:
        t.p("このAPIは現在、新規の利用申請を受け付けていません。")
        return
    application_panel(a, ctx["me"])


def application_panel(a, me):
    with t.section(classes="box"):
        field(
            "利用プロジェクト",
            "project",
            required=True,
            options=[(p, p) for p in me["projects"]] + [(me["personal_project"], "個人ワークスペース")],
        )
        field(
            "申請対象",
            "grant-kind",
            required=True,
            options=[("project", "プロジェクト全員"), ("personal", "自分だけ")],
        )
        product_views.application_form(a, field)
        field("利用目的", "reason", textarea=True, required=True)
        btn("申請する", apply, a, primary=True)


SCREENS = (
    Screen(
        "apply/",
        "利用申請",
        application_page,
        load_application,
        own_heading=True,
        examples={"apply": lambda: application_panel(example.ASSET, example.USER)},
    ),
)
