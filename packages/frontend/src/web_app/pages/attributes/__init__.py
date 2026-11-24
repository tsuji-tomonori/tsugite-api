# 属性値の画面を定義する。
from actions.workspace import attribute_menu, load_workspace
from components.workspace import page_title, view
from routing.screen_registry import Screen

SCREENS = (
    Screen(
        "attributes/",
        page_title,
        view,
        load_workspace,
        group="メタデータ",
        order=63,
        menu_paths=attribute_menu,
    ),
)
