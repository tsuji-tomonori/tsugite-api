# アクセスログ画面の部品とルートを定義する。
from actions.logs import load_logs
from components.logs import logs_view, request_lookup
from routing.screen_registry import Screen

SCREENS = (
    Screen(
        "logs",
        "アクセスログ",
        logs_view,
        load_logs,
        group="ガバナンス",
        order=140,
        description="自分が呼び出したAPIの記録を確認できます。",
        clear_on_load=("log_rows", "dims", "workspace"),
        examples={"logs": lambda: request_lookup("example-request")},
    ),
)
