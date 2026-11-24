# 監査履歴詳細画面の部品とルートを定義する。
from actions.logs import load_detail
from components.logs import detail_view
from routing.screen_registry import Screen

SCREENS = (
    Screen(
        "audit-logs/",
        "監査履歴詳細",
        detail_view,
        load_detail,
        parent="audit-logs",
        clear_on_load=("log_detail",),
    ),
)
