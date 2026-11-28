# ブラウザーとサーバーで共用するログ形式を定義する。
"""Application log contract shared with the browser build (standard library only)."""

import re
from datetime import UTC, datetime
from typing import TypedDict

INVOKE_ROUTE = "/api/invoke/{key}/{environment}/{project}/{tail:path}"

SCREENS = frozenset(
    {
        "home",
        "dashboard",
        "inquiries",
        "guide",
        "keys",
        "workspace",
        "attributes",
        "metadata",
        "departments",
        "projects",
        "metrics",
        "logs",
        "members",
        "profile",
        "member-profile",
        "notifications",
        "alerts",
        "catalog",
        "console",
        "mine",
        "inventory",
        "inbox",
        "audit",
        "api",
        "apply",
        "edit",
        "register",
        "login",
    }
)


class LogRecord(TypedDict):
    """ブラウザーとAPIが共有するログの項目と型。"""

    at: str
    level: str
    event: str
    source: str
    reason: str | None
    request_id: str | None
    method: str | None
    route: str | None
    operation: str | None
    screen: str | None
    status: int | None
    actor_id: str | None
    target_subject_id: str | None
    asset_id: str | None
    operator_action: str | None


def identifier(value: object) -> str | None:
    if (
        isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9_:/+@.-]{1,180}", value)
        and not value.startswith(("tsu_", "tst_", "eyJ"))
    ):
        return value
    return None


def log_record(
    event: str,
    *,
    source: str,
    status: int | None = None,
    failed: bool = False,
    user_error: bool = False,
    action: str | None = None,
    request_id: str | None = None,
    method: str | None = None,
    route: str | None = None,
    operation: str | None = None,
    screen: str | None = None,
    actor_id: str | None = None,
    target_subject_id: str | None = None,
    asset_id: str | None = None,
    reason: str | None = None,
) -> LogRecord:
    if action:
        level = "CRITICAL"
    elif failed or (status is not None and status >= 500):
        level = "ERROR"
    elif user_error or (status is not None and status >= 400):
        level = "WARN"
    else:
        level = "INFO"
    if reason is None and status is not None and status >= 400:
        reason = f"http_{status}"
    return {
        "at": datetime.now(UTC).isoformat(),
        "level": level,
        "event": event,
        "source": source,
        "reason": reason,
        "request_id": identifier(request_id),
        "method": method,
        "route": route,
        "operation": operation,
        "screen": screen if screen in SCREENS else None,
        "status": status,
        "actor_id": identifier(actor_id),
        "target_subject_id": identifier(target_subject_id),
        "asset_id": identifier(asset_id),
        "operator_action": action,
    }
