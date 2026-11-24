# メトリクス画面の部品とルートを定義する。
from components.activity_filters import filter_form
from components.metrics import metrics_view
from content import guide_examples as example
from routing.screen_registry import Screen
from runtime.portal_ui import INITIAL_STATE

from .data import load_metrics

SCREENS = (
    Screen(
        "metrics",
        "メトリクス",
        metrics_view,
        load_metrics,
        group="ガバナンス",
        order=130,
        examples={
            "metrics": lambda: filter_form(
                True, INITIAL_STATE["filters"], [example.DIMENSION], {"units": [], "leads": []}
            )
        },
        clear_on_load=("metrics",),
    ),
)
