# APIの詳細画面の部品とルートを定義する。
from actions.listing_data import load_listing
from components import api_docs, operation_views
from components.controls import btn, field
from components.listing_detail import detail_page, policy_form, publication_actions
from content import guide_examples as example
from routing.portal_navigation import load
from routing.screen_registry import Screen

SCREENS = (
    Screen(
        "api/",
        "APIの詳細",
        detail_page,
        load_listing,
        own_heading=True,
        examples={
            "edit": lambda: publication_actions(example.ASSET),
            "visibility": lambda: policy_form(
                example.ASSET, example.POLICY, [example.PROJECT], expanded=True
            ),
            "operations": lambda: operation_views.provider_view(
                example.ASSET, example.OPERATIONS, field, btn, load
            ),
            "invoke": lambda: api_docs.view(
                example.ASSET,
                [{**example.REQUEST, "status": "approved"}],
                [example.KEY],
                subject=example.USER["subject"],
                personal_project=example.USER["personal_project"],
            ),
        },
    ),
)
