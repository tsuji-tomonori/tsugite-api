# 掲載内容を編集画面の部品とルートを定義する。
from actions.listing_data import load_listing
from components.listing_editor import editor
from routing.screen_registry import Screen

SCREENS = (Screen("edit/", "掲載内容を編集", editor, load_listing),)
