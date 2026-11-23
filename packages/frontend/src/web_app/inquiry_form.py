"""運営への問い合わせフォームと、再送時も同じ受付番号を使う送信処理。"""

import client
from js import window
from puepy import t


async def post_inquiry(state, question: str) -> str:
    if not 2 <= len(question) <= 2000:
        raise client.InputError("問い合わせ内容を2〜2000文字で入力してください。")
    if state.get("draft") != question:
        state.update(draft=question, inquiry_id=str(window.crypto.randomUUID()))
    record = await client.api(
        "/inquiries", "POST", {"inquiry_id": state["inquiry_id"], "question": question}
    )
    state.update(draft="", contact_text="", inquiry_id=None, inquiry_error="")
    return record["inquiry_id"]


def inquiry_form(state, on_submit):
    def remember(event):
        state["contact_text"] = str(event.target.value)

    with t.form(classes="chat-inquiry", on_submit=on_submit):
        t.p("運営担当者に送信します。回答は「自分の問い合わせ」で確認できます。")
        if error := state.get("inquiry_error"):
            t.p(error, role="alert")
        with t.label(classes="field"):
            t.span("問い合わせ内容（必須）")
            t.textarea(
                state.get("contact_text", ""),
                id="inquiry-question",
                classes="form-control",
                minlength=2,
                maxlength=2000,
                required=True,
                disabled=state.get("sending", False),
                on_input=remember,
            )
        t.button(
            "問い合わせを送信",
            type="submit",
            classes="btn btn-primary",
            disabled=state.get("sending", False),
        )
