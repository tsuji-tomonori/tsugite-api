"""部署一覧画面の部品とルートを定義する。"""

from actions.workspace import load_workspace
from components.workspace import list_heading
from routing.screen_registry import Screen

SCREENS = (
    Screen(
        "departments",
        "部署",
        lambda: list_heading("departments"),
        load_workspace,
        group="メタデータ",
        order=60,
        own_heading=True,
    ),
)
