import client
from management_targets import load_targets, target_options
from portal_navigation import load
from portal_ui import btn, ctx, field, value
from puepy import t
from screen_registry import Screen


async def send_notice():
    if ctx["me"]["admin"]:
        project, asset = value("notify-project"), ""
    else:
        asset, project, _ = value("notify-target").split("/")
    await client.api(
        "/notifications",
        "POST",
        {
            "title": value("notify-title"),
            "body": value("notify-body"),
            "asset_id": asset,
            "project": project,
        },
    )
    await load()
    ctx["message"] = "通知を送信しました"


async def read_notice(key):
    await client.api("/notifications/" + key + "/read", "PUT")
    await load()


async def more_notices(offset):
    ctx["notice_offset"] = offset
    await load()


def notices_view():
    me = ctx["me"]
    rows = ctx["notices"]["items"]
    if me["admin"] or me["owners"] and ctx.get("targets"):
        with t.details(classes="box"):
            t.summary("利用者に通知を送る")
            if me["admin"]:
                field(
                    "送信先",
                    "notify-project",
                    options=[("*", "全プロジェクト")] + [(p, p) for p in me["known_projects"]],
                )
            else:
                field("送信先のAPIと利用プロジェクト", "notify-target", options=target_options())
            field("件名", "notify-title")
            field("お知らせ本文", "notify-body", textarea=True)
            btn("通知を送信", send_notice, primary=True)
    if not rows:
        t.p("届いている通知はありません。", classes="empty")
    for n in rows:
        with t.article(classes="box"):
            t.small(
                ("未読" if n["unread"] else "既読") + " · " + n["at"][:16].replace("T", " ") + " UTC",
                classes="muted",
            )
            t.h2(n["title"])
            t.p(n["body"])
            t.small("送信者 " + n["sender"] + "　宛先 " + n["project"])
            if n["unread"]:
                btn("既読にする", read_notice, n["id"])
    if ctx.get("notice_offset", 0):
        btn("新しい通知", more_notices, ctx["notice_offset"] - 30)
    if len(rows) == 30:
        btn("以前の通知", more_notices, ctx.get("notice_offset", 0) + 30)


async def load_notifications(_page):
    await load_targets()
    ctx["notices"] = await client.api("/notifications?offset=" + str(ctx.get("notice_offset", 0)))


SCREENS = (
    Screen("notifications", "通知", notices_view, load_notifications, group="ワークスペース", order=50),
)
