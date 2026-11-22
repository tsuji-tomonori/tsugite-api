from datetime import UTC, datetime

from app.apis.catalog.common import DB, User
from app.apis.schemas import Audit
from app.core.workspace import private_project
from fastapi import APIRouter, Query
from sqlalchemy import or_, select
from tsugite_db.models import AccessLog, Event, LogUnit

router = APIRouter()


@router.get("/audit", response_model=list[Audit], operation_id="audit")
def audit(
    actor: User,
    db: DB,
    asset_id: str = "",
    request_id: str = "",
    action: str = "",
    until: datetime | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    stmt = select(Event)
    led_trace = False
    if request_id and actor.leads:
        log = db.get(AccessLog, request_id)
        if log:
            scopes = set(db.scalars(select(LogUnit.unit_id).where(LogUnit.request_id == request_id))) | {
                log.project
            }
            led_trace = bool(actor.leads & scopes)
    if not (actor.auditor or actor.admin or led_trace):
        stmt = stmt.where(
            or_(
                Event.owner.in_(actor.owners),
                Event.project.in_(actor.projects | {private_project(actor.subject)}),
            )
        )
    if until:
        stmt = stmt.where(Event.at <= until.astimezone(UTC))
    if asset_id:
        stmt = stmt.where(Event.asset_id == asset_id)
    if action:
        stmt = stmt.where(Event.action == action)
    if request_id:
        stmt = stmt.where(Event.request_id == request_id)
    return list(db.scalars(stmt.order_by(Event.at.desc(), Event.id.desc()).offset(offset).limit(limit)))
