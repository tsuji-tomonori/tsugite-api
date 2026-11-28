"""未ログイン時の画面を組み立てる。"""

from __future__ import annotations

from components.login import login_panel


def login_page() -> None:
    """設定済みのログイン部品を表示する。"""
    login_panel()
