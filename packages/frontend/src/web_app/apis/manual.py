# 手動HTTPリクエストの入力を検証する。
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from apis import client

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")


def request_options(url: str, method: str, raw_headers: str, body: str) -> dict[str, Any]:
    """URL・ヘッダー・本文を検証して送信オプションを作る。"""
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
