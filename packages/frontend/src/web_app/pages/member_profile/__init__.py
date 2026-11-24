# 利用者のプロフィール画面の部品とルートを定義する。
from actions.profile import load_profile
from components.profile import view
from routing.screen_registry import Screen

SCREENS = (
    Screen(
        "member-profile/",
        "利用者のプロフィール",
        view,
        load_profile,
        parent="members",
        clear_on_load=("member_profile", "profile_directory"),
    ),
)
