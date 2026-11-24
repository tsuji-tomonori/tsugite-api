# アラート画面の部品とルートを定義する。
from components.alerts import alerts_view, rule_form
from content import guide_examples as example
from routing.screen_registry import Screen

from .data import load_alerts

SCREENS = (
    Screen(
        "alerts",
        "アラート",
        alerts_view,
        load_alerts,
        group="ガバナンス",
        order=150,
        examples={"alerts": lambda: rule_form(example.TARGETS, expanded=True)},
    ),
)
