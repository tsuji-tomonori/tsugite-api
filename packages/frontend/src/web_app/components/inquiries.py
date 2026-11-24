# 問い合わせの履歴と返信欄を表示する。
from __future__ import annotations

from actions.inquiries import inquiry_page, reply_inquiry, submit_inquiry
from puepy import t
from runtime.portal_ui import action, ctx

from components.controls import btn
from components.inquiry_form import inquiry_form


def inquiries() -> None:
    """受付履歴と権限に応じた回答欄を描画する。"""
    admin_view = ctx.get("inquiry_incoming", False)
    if ctx["me"]["admin"]:
        with t.div(classes="chat-actions"):
            btn("自分の問い合わせ", inquiry_page, False, 0, primary=not admin_view)
            btn("運営への問い合わせ", inquiry_page, True, 0, primary=admin_view)
    if not admin_view:
        state = ctx.setdefault("inquiry_form", {})
        with t.section(classes="box"):
            t.h2("新しい問い合わせ")
            if receipt := state.get("receipt"):
                t.p("問い合わせを受け付けました。受付番号 " + receipt, role="status")
            inquiry_form(state, action(submit_inquiry))
        t.h2("自分の問い合わせ")
    entries = ctx.get("inquiries", [])
    if not entries:
        t.p("問い合わせはありません。", classes="empty")
    for record in entries[:20]:
        key = record["inquiry_id"]
        with t.article(classes="box chat-ticket"):
            t.small("受付番号 " + key)
            t.p(record["question"], classes="chat-text")
            if record["answer"]:
                t.h3("運営からの回答")
                t.p(record["answer"], classes="chat-text")
            elif admin_view:
                with t.label(classes="field"):
                    t.span("回答")
                    t.textarea(id="reply-" + key, classes="form-control", minlength=2, maxlength=2000)
                btn("回答を送信", reply_inquiry, key, primary=True)
            else:
                t.small("回答待ち", classes="muted")
    offset = ctx.get("inquiry_offset", 0)
    with t.div(classes="chat-actions"):
        if offset:
            btn("前へ", inquiry_page, admin_view, max(0, offset - 20))
        if len(entries) > 20:
            btn("次へ", inquiry_page, admin_view, offset + 20)
