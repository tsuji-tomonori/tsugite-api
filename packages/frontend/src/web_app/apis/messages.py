# 通知・チャット・問い合わせのAPIを呼び出す。
from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote, urlencode

from js import window

from apis import client


async def inquiry(data: dict[str, Any]) -> dict[str, Any]:
    """受付番号付きの問い合わせを送る。"""
    return await client.request_object("/inquiries", "POST", data)


async def inquiries(params: dict[str, Any]) -> list[dict[str, Any]]:
    """問い合わせ一覧を取得する。"""
    return await client.request_rows("/inquiries?" + urlencode(params))


async def reply(key: str, data: dict[str, Any]) -> None:
    """問い合わせの回答を送る。"""
    await client.api("/inquiries/" + key + "/reply", "PUT", data)


async def notice(data: dict[str, Any]) -> None:
    """通知を配信する。"""
    await client.api("/notifications", "POST", data)


async def read(key: str) -> None:
    """通知を既読にする。"""
    await client.api("/notifications/" + key + "/read", "PUT")


async def notices(offset: int) -> dict[str, Any]:
    """受信した通知を取得する。"""
    return await client.request_object("/notifications?offset=" + str(offset))


async def unread() -> dict[str, Any]:
    """未読件数を取得する。"""
    return await client.request_object("/notifications/count")


async def chat(data: dict[str, Any]) -> dict[str, Any]:
    """チャットの質問を送る。"""
    return await client.request_object("/chat", "POST", data)


async def get_answer(job_id: str) -> dict[str, Any]:
    """チャットの処理結果を取得する。"""
    return await client.request_object("/chat?job_id=" + quote(job_id, safe=""))


async def post_inquiry(state: dict[str, Any], question: str) -> str:
    """再送時に受付番号を引き継いで問い合わせる。"""
    if not 2 <= len(question) <= 2000:
        raise client.InputError("問い合わせ内容を2〜2000文字で入力してください。")
    if state.get("draft") != question:
        state.update(draft=question, inquiry_id=str(window.crypto.randomUUID()))
    record = await inquiry({"inquiry_id": state["inquiry_id"], "question": question})
    state.update(draft="", contact_text="", inquiry_id=None, inquiry_error="")
    receipt: str = record["inquiry_id"]
    return receipt


async def wait_for_result(job_id: str) -> dict[str, Any]:
    """回答または待機期限まで処理結果を確認する。"""
    for attempt in range(35):
        if attempt:
            await asyncio.sleep(min(attempt, 5))
        answer = await get_answer(job_id)
        if answer["kind"] != "pending":
            return answer
    return {"kind": "error", "answer": "回答に時間がかかっています。時間をおいて再度お試しください。"}
