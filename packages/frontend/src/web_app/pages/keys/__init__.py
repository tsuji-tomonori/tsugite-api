"""APIキー画面の部品とルートを定義する。"""

from components import credential_views
from components.controls import btn, field
from components.keys import key_form, keys_view
from content import guide_examples as example
from routing.portal_navigation import load
from routing.screen_registry import Screen

from .data import load_keys

SCREENS = (
    Screen(
        "keys",
        "APIキー",
        keys_view,
        load_keys,
        group="ワークスペース",
        order=30,
        examples={
            "keys": lambda: key_form(example.PROJECTS, [example.ASSET], None, expanded=True),
            "credential": lambda: credential_views.render_form(
                {"me": example.USER}, example.PROJECT["id"], example.OPTIONS, field, btn, load
            ),
            "rotate": lambda: credential_views.credentials_view(
                {"me": example.USER, "workspace": {"admin": False, "leads": []}, "keys": [example.KEY]},
                field,
                btn,
                load,
                [],
            ),
        },
    ),
)
