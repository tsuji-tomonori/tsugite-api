# APIカタログ画面の部品とルートを定義する。
from actions.catalog import load_catalog
from components.catalog import cards
from routing.screen_registry import Screen

SCREENS = (
    Screen(
        "catalog",
        "APIカタログ",
        cards,
        load_catalog,
        group="ワークスペース",
        order=20,
    ),
)
