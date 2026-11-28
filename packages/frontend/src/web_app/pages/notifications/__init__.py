"""通知画面の部品とルートを定義する。"""

from components.notifications import notice_form, notices_view
from content import guide_examples as example
from routing.screen_registry import Screen

from .data import load_notifications

SCREENS = (
    Screen(
        "notifications",
        "通知",
        notices_view,
        load_notifications,
        group="ワークスペース",
        order=50,
        examples={"notice": lambda: notice_form(example.USER, example.TARGETS, expanded=True)},
    ),
)
