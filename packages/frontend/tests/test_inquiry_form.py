# 応答を受け取れずに再送しても受付番号を再利用し、次の新規送信には別の番号を使う。
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


def test_retry_reuses_pending_inquiry_id(portal_module, monkeypatch):
    """応答を受け取れずに再送しても受付番号を再利用し、次の新規送信には別の番号を使う。"""
    form = portal_module("inquiry_form")
    uuid = Mock(side_effect=["first", "second", "third"])
    monkeypatch.setattr(form.window, "crypto", SimpleNamespace(randomUUID=uuid), raising=False)
    api = AsyncMock(side_effect=[OSError("通信失敗"), {"inquiry_id": "first"}, {"inquiry_id": "second"}])
    monkeypatch.setattr(form.client, "api", api)
    state = {"contact_text": "利用方法について"}
    question = state["contact_text"]
    with pytest.raises(OSError, match="通信失敗"):
        asyncio.run(form.post_inquiry(state, question))
    assert state["contact_text"] == question
    assert asyncio.run(form.post_inquiry(state, question)) == "first"
    assert state["contact_text"] == ""
    assert asyncio.run(form.post_inquiry(state, question)) == "second"
    assert [call.args for call in api.await_args_list] == [
        ("/inquiries", "POST", {"inquiry_id": key, "question": question})
        for key in ("first", "first", "second")
    ]


def test_invalid_question_is_not_submitted(portal_module, monkeypatch):
    """短すぎる本文と文字数の上限を超えた本文は運営へ送信しない。"""
    form = portal_module("inquiry_form")
    api = AsyncMock()
    monkeypatch.setattr(form.client, "api", api)
    for question in ("", "問", "問" * 2001):
        with pytest.raises(form.client.InputError, match="2〜2000文字"):
            asyncio.run(form.post_inquiry({}, question))
    api.assert_not_awaited()


def test_inquiries_page_shows_receipt_and_latest_tickets(portal_module, monkeypatch):
    """自分の履歴の2ページ目から送信すると、受付番号と先頭ページの新しい問い合わせが表示される。"""
    from unittest.mock import patch
    from xml.dom.minidom import Document

    from puepy import Page
    from puepy.core import Tag

    screen = portal_module("portal_pages.inquiries")
    screen.ctx.update(me={"admin": True}, inquiry_offset=20)

    class InquiryPage(Page):
        def populate(self):
            screen.inquiries()

    def visible_text():
        page = InquiryPage()
        with page:
            page.generate_children()
        with patch.object(Tag, "document", Document()):
            elements = page.render().getElementsByTagName("*")
            return [
                node.data for el in elements for node in el.childNodes if node.nodeType == node.TEXT_NODE
            ]

    assert "新しい問い合わせ" in visible_text()
    question = "利用手順について"
    record = {"inquiry_id": "abc", "question": question, "answer": None}
    api = AsyncMock(side_effect=[record, [record]])
    monkeypatch.setattr(screen.client, "api", api)
    monkeypatch.setattr(screen, "value", lambda name: question)
    window = portal_module("inquiry_form").window
    monkeypatch.setattr(window, "crypto", SimpleNamespace(randomUUID=lambda: "abc"), raising=False)
    asyncio.run(screen.submit_inquiry())
    assert api.await_args_list[-1].args == ("/inquiries?incoming=false&offset=0",)
    result = visible_text()
    assert "問い合わせを受け付けました。受付番号 abc" in result and "回答待ち" in result
    assert question in result
    screen.ctx["inquiry_incoming"] = True
    inbox = visible_text()
    assert "問い合わせを送信" not in inbox and "回答を送信" in inbox
