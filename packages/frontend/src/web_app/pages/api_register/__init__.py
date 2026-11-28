"""APIを登録画面の部品とルートを定義する。"""

from actions.listing_editor import load_directory
from components.listing_editor import editor, listing_identity
from routing.screen_registry import Screen

SCREENS = (
    Screen(
        "register",
        "APIを登録",
        editor,
        load_directory,
        parent="inventory",
        examples={"publish": lambda: listing_identity({})},
    ),
)
