import chat_views
from portal_ui import ctx, render
from screen_registry import Screen

SCREENS = (
    Screen("home", "ホーム", lambda: chat_views.home(ctx, render), group="ワークスペース", order=10),
)
