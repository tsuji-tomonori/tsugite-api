import guide_views
from portal_navigation import go
from portal_ui import btn, ctx, route
from screen_registry import Screen, screens


def article_id():
    return route().split("/", 1)[1]


def article_title():
    guide = guide_views.BY_ID.get(article_id())
    return guide.title if guide else "使い方ガイド"


def article():
    titles = {path: screen.title for path, screen in screens().items() if screen.group}
    guide_views.article(article_id(), ctx["me"], titles, go, btn)


SCREENS = (
    Screen("guide", "使い方ガイド", lambda: guide_views.index(ctx), group="ヘルプ", order=80),
    Screen("guide/", article_title, article, parent="guide"),
)
