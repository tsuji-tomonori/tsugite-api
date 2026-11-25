# 障害の原因と対処情報を記録する。
"""Operational errors carry only operator-authored instructions into application logs."""

import json
import logging
from datetime import UTC, datetime
from time import monotonic

from app.core.log_record import INVOKE_ROUTE, log_record
from fastapi import HTTPException

logger = logging.getLogger("tsugite.access")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.propagate = False


def emit(event, **fields):
    record = log_record(event, **fields)
    logger.log(getattr(logging, record["level"]), json.dumps(record, ensure_ascii=False))


class InvocationTimer:
    def __init__(self):
        self.started_at = datetime.now(UTC)
        self.started = monotonic()

    def finish(self, source, screen, status, **fields):
        responded_at = datetime.now(UTC)
        elapsed = round((monotonic() - self.started) * 1000)
        return {
            "at": responded_at,
            "duration_ms": elapsed,
            "diagnostics": invocation_details(
                source, screen, status, started_at=self.started_at, responded_at=responded_at, **fields
            ),
        }


def invocation_details(source, screen, status, *, started_at=None, responded_at=None, **fields):
    record = log_record(
        "invoke.authorization" if source == "authorizer" else "http.access",
        source=source,
        screen=screen,
        status=status,
        **fields,
    )
    data = {
        key: record[key] for key in ("event", "source", "screen", "level", "reason", "operator_action")
    }
    if started_at is not None and responded_at is not None:
        data.update(started_at=started_at.isoformat(), responded_at=responded_at.isoformat())
    return json.dumps(data, ensure_ascii=False)


def exported_invocation(row, data):
    record = log_record(
        "http.access", source="api", route=INVOKE_ROUTE, actor_id=row.actor, status=row.status
    )
    if row.diagnostics:
        record.update(json.loads(row.diagnostics))
    return {**record, **data}


class OperationalRepair(HTTPException):
    def __init__(
        self, reason, action, *, asset_id=None, detail="管理者による復旧が必要です", status=503
    ):
        super().__init__(status, detail)
        self.fields = {"reason": reason, "action": action}
        if asset_id is not None:
            self.fields["asset_id"] = asset_id


def asset_object(asset, column):
    """Decode an object stored in the catalog, preserving the row needed for a patch."""
    try:
        value = json.loads(getattr(asset, column))
        if not isinstance(value, dict):
            raise ValueError("expected object")
        return value
    except (ValueError, TypeError) as exc:
        raise OperationalRepair(
            "invalid_asset_" + column,
            f"assets.id がログの asset_id と一致する行を特定し、{column} を登録元の正しいJSONオブジェクトと照合して復元する。修正後に同じAPIを再確認する。",
            asset_id=asset.id,
        ) from exc
