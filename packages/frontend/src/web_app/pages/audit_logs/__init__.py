# 監査履歴画面の部品とルートを定義する。
from actions.logs import can_audit, load_logs
from components.logs import logs_view
from routing.screen_registry import Screen

SCREENS = (
    Screen(
        "audit-logs",
        "監査履歴",
        lambda: logs_view("audit"),
        load_logs,
        group="ガバナンス",
        order=145,
        visible=can_audit,
        description="担当する部署・プロジェクトのAPI呼び出しを確認できます。管理者と監査担当は全体を確認できます。",
        clear_on_load=("log_rows", "dims", "workspace"),
    ),
)
