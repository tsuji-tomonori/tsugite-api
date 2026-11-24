# アクセスログ詳細画面の部品とルートを定義する。
from actions.logs import load_detail
from components.logs import detail_view
from routing.screen_registry import Screen

SCREENS = (
    Screen(
        "logs/",
        "アクセスログ詳細",
        detail_view,
        load_detail,
        parent="logs",
        clear_on_load=("log_detail",),
    ),
)
