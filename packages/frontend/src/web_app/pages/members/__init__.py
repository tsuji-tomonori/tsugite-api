# ユーザー管理画面の部品とルートを定義する。
from __future__ import annotations

from components.members import invite_form, members_view
from content import guide_examples as example
from routing.screen_registry import Screen
from runtime.portal_ui import ctx

from .data import load_members


def view() -> None:
    """権限と読み込み状態に応じて管理欄を表示する。"""
    if ctx["me"]["admin"]:
        members_view()


SCREENS = (
    Screen(
        "members",
        "ユーザー管理",
        view,
        load_members,
        group="管理",
        order=100,
        examples={"member": lambda: invite_form([example.PROJECT["id"]])},
        visible=lambda user: user["admin"],
    ),
)
