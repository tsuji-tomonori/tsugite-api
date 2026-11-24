# プロジェクト一覧画面の部品とルートを定義する。
from actions.workspace import load_workspace
from components.workspace import list_heading
from routing.screen_registry import Screen

SCREENS = (
    Screen(
        "projects",
        "プロジェクト",
        lambda: list_heading("projects"),
        load_workspace,
        group="メタデータ",
        order=61,
        own_heading=True,
    ),
)
