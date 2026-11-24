# 問い合わせの送受信とページ移動を扱う。
from __future__ import annotations

from typing import Any

from apis import client
from apis import messages as messages_api
from apis.messages import post_inquiry
from routing.portal_navigation import load
from runtime.portal_ui import ctx, value


async def inquiry_page(incoming: bool, offset: int) -> None:
    """自分の履歴と受信一覧を切り替える。"""
    ctx.update(inquiry_incoming=incoming, inquiry_offset=offset)
    await load()


async def submit_inquiry() -> None:
    """問い合わせを送り受付結果を表示する。"""
    state: dict[str, Any] = ctx["inquiry_form"]
    state.pop("receipt", None)
    receipt = await post_inquiry(state, value("inquiry-question"))
    if ctx.get("inquiry_form") is state:
        state["receipt"] = receipt
        ctx["inquiry_offset"] = 0
        await load_inquiries("inquiries")


async def reply_inquiry(key: str) -> None:
    """選択した問い合わせに回答する。"""
    answer = value("reply-" + key)
    if len(answer) < 2:
        raise client.InputError("回答を入力してください")
    await messages_api.reply(key, {"answer": answer})
    await load()


async def load_inquiries(_page: str) -> None:
    """表示中の問い合わせ一覧を取得する。"""
    params = {
        "incoming": str(ctx.get("inquiry_incoming", False)).lower(),
        "offset": ctx.get("inquiry_offset", 0),
    }
    ctx["inquiries"] = await messages_api.inquiries(params)


async def change_scope() -> None:
    """表示対象を切り替え、先頭の問い合わせから取得する。"""
    await inquiry_page(value("inquiry-scope") == "incoming", 0)
