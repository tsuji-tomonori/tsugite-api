"""プロジェクトの作成画面を組み立てる。"""

from actions.workspace import load_workspace
from components.workspace import page_title, view
from routing.screen_registry import Screen

SCREENS = (Screen("projects/create", page_title, view, load_workspace, parent="projects"),)
