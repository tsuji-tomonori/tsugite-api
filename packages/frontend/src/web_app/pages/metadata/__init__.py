"""属性一覧の画面を定義する。"""

from actions.workspace import load_workspace
from components.metadata import field_list
from routing.screen_registry import Screen

SCREENS = (Screen("metadata", "属性一覧", field_list, load_workspace, group="メタデータ", order=62),)
