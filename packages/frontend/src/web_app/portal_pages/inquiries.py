from urllib.parse import urlencode

import client
from inquiry_form import inquiry_form, post_inquiry
from portal_navigation import load
from portal_ui import action, btn, ctx, value
from puepy import t
from screen_registry import Screen


async def inquiry_page(incoming, offset):
    ctx.update(inquiry_incoming=incoming, inquiry_offset=offset)
    await load()


async def submit_inquiry() -> None:
    state = ctx["inquiry_form"]
    state.pop("receipt", None)
    receipt = await post_inquiry(state, value("inquiry-question"))
    if ctx.get("inquiry_form") is state:
        state["receipt"] = receipt
        ctx["inquiry_offset"] = 0
        await load_inquiries("inquiries")


async def reply_inquiry(key):
    answer = value("reply-" + key)
    if len(answer) < 2:
        raise client.InputError("回答を入力してください")
    await client.api("/inquiries/" + key + "/reply", "PUT", {"answer": answer})
    await load()


async def load_inquiries(_page):
    params = {
        "incoming": str(ctx.get("inquiry_incoming", False)).lower(),
        "offset": ctx.get("inquiry_offset", 0),
    }
    ctx["inquiries"] = await client.api("/inquiries?" + urlencode(params))


def inquiries():
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


SCREENS = (Screen("inquiries", "問い合わせ", inquiries, load_inquiries, group="ヘルプ", order=90),)
