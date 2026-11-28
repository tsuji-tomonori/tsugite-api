"""ブラウザーからのHTTP送信とトークン交換を扱う。"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

from pyodide.http import pyfetch

from apis import client

CREDENTIAL_MODES = {"bearer": "短期Bearer", "app": "アプリ", "system": "システム"}


async def credential_headers(key: dict[str, Any] | None) -> dict[str, str]:
    """選択した認証情報を短期トークンと交換する。"""
    access = client.store.getItem("access")
    if not access or not key or key.get("mode") not in CREDENTIAL_MODES:
        raise client.InputError("ログイン状態と選択した認証情報を確認してください")
    issued = await pyfetch(
        client.prefix + "/credentials/" + quote(key["id"], safe="") + "/token-exchange",
        method="POST",
        headers={**client.screen_headers(), "Content-Type": "application/x-www-form-urlencoded"},
        body=urlencode(
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
                "subject_token": str(access),
            }
        ),
    )
    payload = await issued.json()
    if not issued.ok:
        raise client.ResponseError(
            f"HTTP {issued.status}　"
            + str(payload.get("error_description", "アクセストークンを取得できませんでした"))
        )
    return {**client.screen_headers(), "Authorization": "Bearer " + payload["access_token"]}


async def fetch(url: str, **options: Any) -> Any:
    """指定されたURLにブラウザーのHTTPリクエストを送る。"""
    return await pyfetch(url, **options)
