# 通知の配信フォームと受信一覧を表示する。
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from actions.management_targets import target_options
from actions.notifications import more_notices, read_notice, send_notice
from puepy import t
from runtime.portal_ui import ctx

from components.controls import btn, field


def notice_form(
    me: dict[str, Any], targets: Sequence[tuple[str, str]], *, expanded: bool = False
) -> None:
    """閲覧者に応じた送信先の選択欄を描画する。"""
    with t.details(classes="box", open=expanded):
        t.summary("利用者に通知を送る")
        if me["admin"]:
            names = me.get("known_project_labels", {})
            field(
                "送信先",
                "notify-project",
                options=[("*", "全プロジェクト")] + [(p, names.get(p, p)) for p in me["known_projects"]],
            )
        else:
            field("送信先のAPIと利用プロジェクト", "notify-target", options=targets)
        field("件名", "notify-title")
        field("お知らせ本文", "notify-body", textarea=True)
        btn("通知を送信", send_notice, primary=True)


def notices_view() -> None:
    """受信通知・既読操作・配信欄を表示する。"""
    me = ctx["me"]
    rows = ctx["notices"]["items"]
    if me["admin"] or me["owners"] and ctx.get("targets"):
        notice_form(me, target_options())
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
