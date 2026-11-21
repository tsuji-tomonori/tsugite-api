from app.apis.catalog.common import DB, User
from app.apis.schemas import Right
from app.core.workspace import delegated
from app.db.models import Access, Asset, Event
from fastapi import APIRouter
from sqlalchemy import select

router = APIRouter()


@router.get("/requests", response_model=list[Right], operation_id="requests")
def requests(actor: User, db: DB, incoming: bool = False, asset_id: str = ""):
    last_decision = (
        select(Event.detail)
        .where(
            Event.asset_id == Access.asset_id,
            Event.project == Access.project,
            Event.environment == Access.environment,
            Event.action.in_(("approve", "reject", "withdraw", "revoke")),
        )
        .order_by(Event.at.desc(), Event.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    stmt = select(Access, Asset, last_decision).join(Asset, Asset.id == Access.asset_id)
    stmt = stmt.where(Asset.removed_at.is_(None))
    if not incoming:
        stmt = stmt.where(
            (Access.subject == actor.subject)
            | (Access.subject.is_(None) & Access.project.in_(actor.projects))
        )
    elif not actor.leads:
        stmt = stmt.where(Asset.owner.in_(actor.owners))
    if asset_id:
        stmt = stmt.where(Access.asset_id == asset_id)
    return [
        Right.model_validate(row).model_copy(
            update={
                "asset_name": asset.name,
                "decision_reason": (row.decision_note or (reason if not row.applicant else None))
                if row.status != "pending"
                else None,
            }
        )
        for row, asset, reason in db.execute(
            stmt.order_by(Asset.name, Access.project, Access.environment)
        )
        if not incoming
        or asset.owner in actor.owners
        or (row.status == "pending" and delegated(db, actor, asset, row))
    ]
