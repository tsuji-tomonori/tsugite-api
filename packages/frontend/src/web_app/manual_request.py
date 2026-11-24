# ブラウザーから、利用者が指定したURLに直接HTTPリクエストを送る。
"""ブラウザーから、利用者が指定したURLに直接HTTPリクエストを送る。"""

import asyncio
import re
from urllib.parse import urlsplit

import client
from js import document
from portal_ui import field
from puepy import t
from pyodide.http import pyfetch

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")


def request_options(url, method, raw_headers, body):
    parts = urlsplit(url)
    if (
        parts.scheme not in ("https", "http")
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or "\\" in url
        or any(char.isspace() or ord(char) < 32 for char in url)
    ):
        raise client.InputError("ユーザー名・パスワードを含まないHTTPまたはHTTPSのURLを入力してください")
    if method not in METHODS:
        raise client.InputError("HTTPメソッドを選んでください")
    headers = {}
    for line in raw_headers.splitlines():
        if not line.strip():
            continue
        name, sep, value = line.partition(":")
        name = name.strip().lower()
        if not sep or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9a-z-]+", name):
            raise client.InputError("ヘッダーは1行に1つ「名前: 値」の形式で入力してください")
        if name in headers:
            raise client.InputError("同じ名前のヘッダーが複数あります")
        headers[name] = value.strip()
    opts = {
        "method": method,
        "headers": headers,
        "credentials": "omit",
        "redirect": "error",
        "referrerPolicy": "no-referrer",
        "cache": "no-store",
    }
    if body:
        if method in ("GET", "HEAD"):
            raise client.InputError(method + "には本文を指定できません")
        opts["body"] = body
    return opts


async def send(button, output):
    try:

        def entered(name):
            return str(document.getElementById("manual-" + name).value)

        url = entered("url").strip()
        options = request_options(url, entered("method"), entered("headers"), entered("body"))
        try:
            response = await pyfetch(url, **options)
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


def submit(event):
    button = event.currentTarget
    if button.disabled:
        return
    button.disabled = True
    button.setAttribute("aria-busy", "true")
    button.textContent = "送信中"
    output = document.getElementById("manual-response")
    output.textContent = "呼び出し中…"
    asyncio.ensure_future(send(button, output))


def view():
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
