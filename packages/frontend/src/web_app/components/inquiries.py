# 問い合わせの履歴と返信欄を表示する。
from __future__ import annotations

from actions.inquiries import change_scope, inquiry_page, reply_inquiry, submit_inquiry
from puepy import t
from runtime.portal_ui import action, ctx

from components.controls import btn
from components.inquiry_form import inquiry_form
from components.list_layout import disclosure, result_table


def inquiries() -> None:
    """受付履歴と権限に応じた回答欄を描画する。"""
    admin_view = ctx.get("inquiry_incoming", False)
    state = ctx.setdefault("inquiry_form", {})
    if not admin_view and (receipt := state.get("receipt")):
        t.p("問い合わせを受け付けました。受付番号 " + receipt, role="status")
    with t.div(classes="list-tools"):
        if ctx["me"]["admin"]:
            with t.select(
                id="inquiry-scope",
                aria_label="問い合わせの表示対象",
                classes="form-select",
                on_change=action(change_scope),
            ):
                t.option("自分の分", value="mine", selected=not admin_view)
                t.option("運営あて", value="incoming", selected=admin_view)
        if not admin_view:
            with disclosure("新しい問い合わせ", expanded=bool(state.get("contact_text"))):
                inquiry_form(state, action(submit_inquiry))
    entries = ctx.get("inquiries", [])
    if not entries:
        t.p("問い合わせはありません。", classes="empty")
    else:
        with result_table(
            "運営への問い合わせ" if admin_view else "自分の問い合わせ",
            ("受付番号", "問い合わせ内容", "回答"),
        ):
            for record in entries[:20]:
                key = record["inquiry_id"]
                with t.tr():
                    t.th(key, scope="row", classes="mono")
                    t.td(record["question"], classes="chat-text")
                    with t.td():
                        if record["answer"]:
                            t.div(record["answer"], classes="chat-text")
                        elif admin_view:
                            with disclosure("回答する"):
                                with t.label(classes="field"):
                                    t.span("回答")
                                    t.textarea(
                                        id="reply-" + key,
                                        classes="form-control",
                                        minlength=2,
                                        maxlength=2000,
                                    )
                                btn("回答を送信", reply_inquiry, key, primary=True)
                        else:
                            t.span("回答待ち", classes="muted")
    offset = ctx.get("inquiry_offset", 0)
    with t.div(classes="chat-actions"):
        if offset:
            btn("前へ", inquiry_page, admin_view, max(0, offset - 20))
        if len(entries) > 20:
            btn("次へ", inquiry_page, admin_view, offset + 20)
