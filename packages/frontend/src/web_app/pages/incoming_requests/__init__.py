# 届いた申請画面の部品とルートを定義する。
from actions.requests import load_requests
from components.requests import rights_page
from content import guide_examples as example
from routing.screen_registry import Screen
from runtime.portal_ui import ctx

SCREENS = (
    Screen(
        "inbox",
        "届いた申請",
        lambda: rights_page(True, ctx["rows"]),
        load_requests,
        examples={"review": lambda: rights_page(True, [example.REQUEST])},
        group="提供者メニュー",
        order=120,
        visible=lambda user: bool(user["owners"] or user["leads"]),
        description="利用目的と環境を確認し、チームに届いた申請を判断します。",
    ),
)
