# ホーム画面の部品とルートを定義する。
from components import chat_views
from routing.screen_registry import Screen
from runtime.portal_ui import ctx, render

SCREENS = (
    Screen("home", "ホーム", lambda: chat_views.home(ctx, render), group="ワークスペース", order=10),
)
