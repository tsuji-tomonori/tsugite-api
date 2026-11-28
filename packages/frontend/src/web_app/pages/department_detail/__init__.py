"""部署詳細画面の部品とルートを定義する。"""

from actions.workspace import load_workspace
from components.workspace import page_title, view
from routing.screen_registry import Screen

SCREENS = (Screen("departments/", page_title, view, load_workspace, parent="departments"),)
