# 業務操作履歴画面の部品とルートを定義する。
from components.audit import audit_search, audit_view
from routing.screen_registry import Screen

from .data import load_audit

SCREENS = (
    Screen(
        "audit",
        "業務操作履歴",
        audit_view,
        load_audit,
        group="ガバナンス",
        order=160,
        examples={"audit": lambda: audit_search("", "approve")},
    ),
)
