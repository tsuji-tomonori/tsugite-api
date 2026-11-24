# 部署の所属設定画面を組み立てる。
from actions.workspace import load_workspace
from components.workspace import membership_panel, page_title, view
from routing.screen_registry import Screen

SCREENS = (
    Screen(
        "departments/member/",
        page_title,
        lambda: view(membership_panel),
        load_workspace,
        parent="departments",
    ),
)
