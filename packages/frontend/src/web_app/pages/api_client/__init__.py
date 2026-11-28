"""APIクライアント画面の部品とルートを定義する。"""

from actions.console import load_console
from components.console import console_view
from routing.screen_registry import Screen

SCREENS = (
    Screen("console", "APIクライアント", console_view, load_console, group="ワークスペース", order=25),
)
