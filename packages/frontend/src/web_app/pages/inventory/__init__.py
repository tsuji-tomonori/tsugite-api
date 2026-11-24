# 提供するAPI画面の部品とルートを定義する。
from actions.catalog import load_catalog
from components.catalog import cards
from components.controls import btn
from routing.portal_navigation import go
from routing.screen_registry import Screen

SCREENS = (
    Screen(
        "inventory",
        "提供するAPI",
        cards,
        load_catalog,
        group="提供者メニュー",
        order=110,
        visible=lambda user: bool(user["owners"]),
        heading_action=lambda: btn("APIを登録", go, "register", primary=True),
    ),
)
