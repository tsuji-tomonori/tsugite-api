# 届いた申請画面の部品とルートを定義する。
from actions.requests import load_requests
from components.requests import inbox, rights_page
from content import guide_examples as example
from routing.screen_registry import Screen

SCREENS = (
    Screen(
        "inbox",
        "届いた申請",
        inbox,
        load_requests,
        examples={"review": lambda: rights_page(True, [example.REQUEST])},
        group="商品提供・審査",
        order=120,
        description="利用目的と環境を確認し、チームに届いた申請を判断します。",
    ),
)
