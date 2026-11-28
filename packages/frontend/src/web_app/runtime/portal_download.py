"""ブラウザーで生成したファイルを保存する。"""

from __future__ import annotations

from typing import Any

from js import document, window


def save_blob(blob: Any, filename: str) -> None:
    """Blobを指定した名前でダウンロードする。"""
    url = window.URL.createObjectURL(blob)
    a = document.createElement("a")
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
