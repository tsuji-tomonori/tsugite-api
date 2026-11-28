"""利用申請画面の部品とルートを定義する。"""

from components.application import application_page, application_panel
from content import guide_examples as example
from routing.screen_registry import Screen

from .data import load_application

SCREENS = (
    Screen(
        "apply/",
        "利用申請",
        application_page,
        load_application,
        own_heading=True,
        examples={"apply": lambda: application_panel(example.ASSET, example.USER)},
    ),
)
