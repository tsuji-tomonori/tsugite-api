"""手動HTTPリクエストの入力を検証する。"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote, urlsplit

from apis import client
from apis.invocation import CREDENTIAL_MODES, credential_headers

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


def selectable_key(key: dict[str, Any], me: dict[str, Any]) -> bool:
    """本人がポータルで使える個人キーと共有キーを選ぶ。"""
    return (
        (key["mode"] == "legacy" or key["mode"] in CREDENTIAL_MODES)
        and not key["revoked"]
        and key.get("can_portal_exchange", True)
        and (key["kind"] == "shared" or key["creator"] == me["subject"])
        and (key["project"] in me["projects"] or key["project"] == me["personal_project"])
        and (not key.get("users") or me["subject"] in key["users"])
    )


async def apply_key(url: str, origin: str, options: dict[str, Any], key: dict[str, Any]) -> None:
    """同一ポータルの呼び出しURLに選択したキーの認証を付ける。"""
    parts = urlsplit(url)
    prefix = client.prefix + "/invoke/"
    segments = parts.path.removeprefix(prefix).split("/")
    if (
        not url.startswith(origin + prefix)
        or len(segments) < 4
        or not all(segments[:3])
        or any(
            decoded in (".", "..") or any(c in decoded for c in ("/", "\\", "%"))
            for decoded in map(unquote, segments)
        )
    ):
        raise client.InputError(
            "APIキーを使うには、このポータルの /api/invoke/ で始まる呼び出しURLを指定してください"
        )
    headers = options["headers"]
    if headers.keys() & {"authorization", "x-api-key", "x-tsugite-key-id", "x-tsugite-screen"}:
        raise client.InputError(
            "APIキーを選ぶ場合は、手入力した認証・画面識別ヘッダーを削除してください"
        )
    options["mode"] = "same-origin"
    if key["mode"] == "legacy":
        access = client.store.getItem("access")
        if not access:
            raise client.InputError("ログインし直してください")
        headers.update(client.screen_headers(), Authorization="Bearer " + str(access))
        headers["X-Tsugite-Key-Id"] = key["id"]
    else:
        headers.update(await credential_headers(key))
