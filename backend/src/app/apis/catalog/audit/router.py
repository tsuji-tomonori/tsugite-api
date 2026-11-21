from app.apis.catalog.common import DB, User
from app.apis.schemas import Audit
from app.db.models import Event
from fastapi import APIRouter, Query
from sqlalchemy import or_, select

router = APIRouter()


@router.get("/audit", response_model=list[Audit], operation_id="audit")
def audit(
    actor: User,
    db: DB,
    asset_id: str = "",
    request_id: str = "",
    action: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    stmt = select(Event)
    if not actor.auditor:
        stmt = stmt.where(or_(Event.owner.in_(actor.owners), Event.project.in_(actor.projects)))
    if asset_id:
        stmt = stmt.where(Event.asset_id == asset_id)
    if action:
        stmt = stmt.where(Event.action == action)
    if request_id:
        stmt = stmt.where(Event.request_id == request_id)
    return list(db.scalars(stmt.order_by(Event.at.desc(), Event.id.desc()).offset(offset).limit(limit)))
