# 使い方ガイド画面の部品とルートを定義する。
from components import guide_views
from routing.screen_registry import Screen
from runtime.portal_ui import ctx

SCREENS = (Screen("guide", "使い方ガイド", lambda: guide_views.index(ctx), group="ヘルプ", order=80),)
