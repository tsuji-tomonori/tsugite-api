"""Application log contract shared with the browser build (standard library only)."""

import re
from datetime import UTC, datetime

INVOKE_ROUTE = "/api/invoke/{key}/{environment}/{project}/{tail:path}"

SCREENS = frozenset(
    {
        "home",
        "dashboard",
        "inquiries",
        "guide",
        "keys",
        "workspace",
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


def identifier(value):
    if (
        isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9_:/+@.-]{1,180}", value)
        and not value.startswith(("tsu_", "tst_", "eyJ"))
    ):
        return value
    return None


def log_record(
    event,
    *,
    source,
    status=None,
    failed=False,
    user_error=False,
    action=None,
    request_id=None,
    method=None,
    route=None,
    operation=None,
    screen=None,
    actor_id=None,
    target_subject_id=None,
    asset_id=None,
    reason=None,
):
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
