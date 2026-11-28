"""アクセスログ画面の部品とルートを定義する。"""

from actions.logs import load_logs
from components.activity_filters import filter_form
from components.logs import logs_view
from routing.screen_registry import Screen
from runtime.portal_ui import INITIAL_STATE

SCREENS = (
    Screen(
        "logs",
        "アクセスログ",
        logs_view,
        load_logs,
        group="ガバナンス",
        order=140,
        clear_on_load=("log_rows", "dims", "workspace"),
        examples={
            "logs": lambda: filter_form(
                False, INITIAL_STATE["filters"], [], {}, scope="personal", request_id="example-request"
            )
        },
    ),
)
