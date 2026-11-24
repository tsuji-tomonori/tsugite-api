# 利用状況画面の部品とルートを定義する。
from components.dashboard import dashboard_view
from routing.screen_registry import Screen

from .data import load_dashboard

SCREENS = (
    Screen(
        "dashboard",
        "利用状況",
        dashboard_view,
        load_dashboard,
        group="ワークスペース",
        order=70,
        clear_on_load=("dashboard", "home_metrics", "recent_logs"),
    ),
)
