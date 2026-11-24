# 部署一覧画面の部品とルートを定義する。
from actions.workspace import load_workspace
from components.workspace import usage_settings, view
from components.workspace_members import membership_editor
from content import guide_examples as example
from routing.screen_registry import Screen

SCREENS = (
    Screen(
        "workspace",
        "部署一覧",
        view,
        load_workspace,
        parent="departments",
        examples={
            "limits": lambda: usage_settings(example.PROJECT, example.LIMIT),
            "suspend": lambda: usage_settings(example.PROJECT, {"me": example.USER}),
            "organization": lambda: membership_editor(
                "projects", example.PROJECT, {"users": [example.USER], "memberships": []}, None, draft={}
            ),
        },
    ),
)
