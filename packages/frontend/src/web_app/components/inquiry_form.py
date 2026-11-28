"""共通の問い合わせフォームを描画する。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from puepy import t


def inquiry_form(
    state: dict[str, Any], on_submit: Callable[[Any], None], *, max_length: int = 2000
) -> None:
    """下書きと入力エラーを含む問い合わせ欄を表示する。"""

    def remember(event: Any) -> None:
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
                maxlength=max_length,
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
