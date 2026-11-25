# ガイド記事と操作先を組み立てる。
from __future__ import annotations

from components import guide_views
from components.controls import btn
from content.guide_content import BY_ID
from routing.portal_navigation import go
from routing.screen_registry import Screen, guide_examples, screens
from runtime.portal_ui import ctx, route


def article_id() -> str:
    """URLから記事識別子を取り出す。"""
    return route().split("/", 1)[1]


def article_title() -> str:
    """記事に対応する画面名を返す。"""
    guide = BY_ID.get(article_id())
    return guide.title if guide else "使い方ガイド"


def article() -> None:
    """記事と操作先をガイド部品に渡す。"""
    titles = {path: screen.page_title() for path, screen in screens().items() if screen.group}
    guide_views.article(article_id(), ctx["me"], titles, go, btn, guide_examples())


SCREENS = (Screen("guide/", article_title, article, parent="guide"),)
