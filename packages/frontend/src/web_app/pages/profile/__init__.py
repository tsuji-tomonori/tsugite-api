# 自分のプロフィール画面の部品とルートを定義する。
from actions.profile import load_profile
from components.profile import view
from routing.screen_registry import Screen

SCREENS = (
    Screen(
        "profile",
        "自分のプロフィール",
        view,
        load_profile,
        group="個人設定",
        order=105,
        clear_on_load=("member_profile",),
    ),
)
