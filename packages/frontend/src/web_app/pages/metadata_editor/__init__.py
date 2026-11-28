"""属性設定の画面を定義する。"""

from actions.workspace import load_workspace
from components.metadata import field_editor
from routing.screen_registry import Screen

SCREENS = (Screen("metadata/", "メタデータ項目の設定", field_editor, load_workspace, parent="metadata"),)
