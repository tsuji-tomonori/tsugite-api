# 部署の編集画面を組み立てる。
from actions.workspace import load_workspace
from components.workspace import edit_panel, page_title, view
from routing.screen_registry import Screen

SCREENS = (
    Screen(
        "departments/edit/", page_title, lambda: view(edit_panel), load_workspace, parent="departments"
    ),
)
