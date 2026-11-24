# 手動HTTPリクエストの操作欄を表示する。
from __future__ import annotations

import asyncio
from typing import Any

from apis import client
from apis.invocation import fetch
from apis.manual import METHODS, request_options
from js import document
from puepy import t

from components.controls import field


async def send(button: Any, output: Any) -> None:
    """入力内容を送信して応答を表示する。"""
    try:

        def entered(name: str) -> str:
            return str(document.getElementById("manual-" + name).value)

        url = entered("url").strip()
        options = request_options(url, entered("method"), entered("headers"), entered("body"))
        try:
            response = await fetch(url, **options)
        except Exception as exc:
            raise client.ResponseError(
                "応答を取得できませんでした。接続先のURL、CORS設定、リダイレクトの有無を確認してください。"
            ) from exc
        body = await response.string()
        output.textContent = f"HTTP {response.status}\n{body[:12000]}"
        if len(body) > 12000:
            output.textContent += "\n（先頭12,000文字まで表示）"
    except Exception as exc:
        output.textContent = str(exc)
    finally:
        button.disabled = False
        button.removeAttribute("aria-busy")
        button.textContent = "指定したURLに送信"


def submit(event: Any) -> None:
    """送信ボタンから非同期処理を起動する。"""
    button = event.currentTarget
    if button.disabled:
        return
    button.disabled = True
    button.setAttribute("aria-busy", "true")
    button.textContent = "送信中"
    output = document.getElementById("manual-response")
    output.textContent = "呼び出し中…"
    asyncio.ensure_future(send(button, output))


def view() -> None:
    """URL・メソッド・ヘッダー・本文の入力欄を表示する。"""
    with t.section(classes="box"):
        t.h2("URLを直接指定")
        t.p("ブラウザーから送信します。認証が必要な場合は、接続先用のヘッダーを入力してください。")
        field("HTTPメソッド", "manual-method", options=[(m, m) for m in METHODS])
        field("リクエストURL（必須）", "manual-url", placeholder="https://api.example.jp/items?limit=10")
        field(
            "ヘッダー（任意）", "manual-headers", textarea=True, placeholder="Accept: application/json"
        )
        field("本文（任意）", "manual-body", textarea=True)
        t.button("指定したURLに送信", type="button", classes="btn btn-primary", on_click=submit)
        t.pre("", id="manual-response", classes="code", aria_live="polite")
