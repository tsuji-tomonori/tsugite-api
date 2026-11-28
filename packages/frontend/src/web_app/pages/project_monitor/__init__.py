"""プロジェクトのモニタリング画面を組み立てる。"""

from actions.workspace import load_workspace
from components.workspace import monitor_panel, page_title, view
from routing.screen_registry import Screen

SCREENS = (
    Screen(
        "projects/monitor/", page_title, lambda: view(monitor_panel), load_workspace, parent="projects"
    ),
)
