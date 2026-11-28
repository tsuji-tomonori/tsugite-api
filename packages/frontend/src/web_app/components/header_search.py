# ヘッダーの入力中にAPIとマニュアルの候補を表示する。
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from apis import products
from apis.client import ResponseError
from content.guide_search import search
from js import document
from puepy import t
from runtime.portal_ui import action

LABEL = "API・マニュアルを検索"
LIMIT = 4


class Suggestions:
    """この検索欄で最後に入力した語句の候補だけを表示する。"""

    def __init__(self) -> None:
        self.revision = 0

    def close(self, form: Any) -> None:
        """保留中の検索を無効にして候補を閉じる。"""
        self.revision += 1
        panel = form.querySelector(".search-suggestions")
        panel.hidden = True
        panel.replaceChildren()

    def input(self, event: Any) -> None:
        """確定した入力を少し待って検索する。"""
        field = event.target
        self.close(field.form)
        query = str(field.value).strip()
        if len(query) >= 2 and not getattr(event, "isComposing", False):
            asyncio.ensure_future(self.update(field, query, self.revision))

    async def update(self, field: Any, query: str, revision: int) -> None:
        """入力と画面が変わっていなければ検索結果を表示する。"""
        await asyncio.sleep(0.25)
        if revision != self.revision or not field.isConnected:
            return
        guides = search(query)[:LIMIT]
        message = ""
        try:
            result = await products.catalog({"q": query, "page": 1})
            rows = result["items"][:LIMIT]
        except ResponseError:
            rows = []
            message = "API候補を取得できませんでした。"
        if revision != self.revision or not field.isConnected:
            return
        panel = field.form.querySelector(".search-suggestions")
        for row in rows:
            self.link(panel, "API", row["name"], "#/api/" + row["id"])
        for guide in guides:
            self.link(panel, "マニュアル", guide.title, "#/guide/" + guide.id)
        if not rows and not guides and not message:
            message = "候補が見つかりませんでした。"
        if message:
            status = document.createElement("div")
            status.textContent = message
            panel.appendChild(status)
        panel.hidden = False

    @staticmethod
    def link(panel: Any, kind: str, title: str, href: str) -> None:
        """候補の種類と題名をリンクとして追加する。"""
        link = document.createElement("a")
        link.href = href
        label = document.createElement("small")
        label.textContent = kind
        link.append(label, title)
        panel.appendChild(link)

    def blur(self, event: Any) -> None:
        """検索欄と候補の外へ移ったら閉じる。"""
        form = event.currentTarget
        if not form.contains(event.relatedTarget):
            self.close(form)

    def keydown(self, event: Any) -> None:
        """上下キーで候補に移り、Escapeで検索欄に戻る。"""
        if event.isComposing or event.key not in ("ArrowDown", "ArrowUp", "Escape"):
            return
        form = event.currentTarget
        panel = form.querySelector(".search-suggestions")
        field = form.querySelector("input")
        if event.key == "Escape":
            event.preventDefault()
            field.focus()
            self.close(form)
            return
        if panel.hidden:
            return
        links = list(panel.querySelectorAll("a"))
        if links:
            event.preventDefault()
            targets = [field, *links]
            index = targets.index(event.target)
            targets[(index + (1 if event.key == "ArrowDown" else -1)) % len(targets)].focus()


def header_search(submit: Callable[[], Awaitable[None]]) -> None:
    """ヘッダーに横断検索欄を描画する。"""
    suggestions = Suggestions()
    with t.form(
        classes="global-search",
        role="search",
        on_submit=action(submit),
        on_focusout=suggestions.blur,
        on_keydown=suggestions.keydown,
    ):
        t.input(
            id="global-query",
            type="search",
            placeholder=LABEL,
            aria_label=LABEL,
            maxlength="120",
            autocomplete="off",
            aria_controls="global-suggestions",
            on_input=suggestions.input,
            on_compositionend=suggestions.input,
        )
        t.div(id="global-suggestions", classes="search-suggestions", hidden=True, aria_live="polite")
