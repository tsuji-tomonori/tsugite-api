# 自分の申請画面の部品とルートを定義する。
from actions.requests import load_requests
from components.requests import rights_page
from content import guide_examples as example
from routing.screen_registry import Screen
from runtime.portal_ui import ctx

SCREENS = (
    Screen(
        "mine",
        "自分の申請",
        lambda: rights_page(False, ctx["rows"]),
        load_requests,
        examples={"status": lambda: rights_page(False, [example.REQUEST])},
        group="ワークスペース",
        order=40,
        description="プロジェクトの申請状況と、承認されたAPIを確認できます。",
    ),
)
