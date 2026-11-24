from datetime import UTC, datetime

from app.core.log_visibility import led_calls
from app.core.workspace import private_project, units
from app.dependencies import DB, User
from app.schemas.catalog import Audit
from fastapi import APIRouter, Query
from sqlalchemy import or_, select
from tsugite_db.models import AccessLog, Event

router = APIRouter()


#: 監査履歴を検索する
@router.get("/audit", response_model=list[Audit], operation_id="audit")
def audit(
    actor: User,
    db: DB,
    #: 対象APIの識別子
    asset_id: str = "",
    #: リクエスト識別子
    request_id: str = "",
    #: 検索する監査操作
    action: str = "",
    #: 監査履歴の検索終了日時
    until: datetime | None = None,
    #: 先頭から読み飛ばす件数
    offset: int = Query(0, ge=0),
    #: 取得件数の上限
    limit: int = Query(100, ge=1, le=500),
):
    stmt = select(Event)
    if not (actor.auditor or actor.admin):
        business_scope = or_(
            Event.owner.in_(actor.owners),
            Event.project.in_(actor.projects | {private_project(actor.subject)}),
        )
        invocation = Event.action.startswith("invoke.")
        call_scope = Event.actor == actor.subject
        if actor.leads:
            calls = select(AccessLog.request_id).where(led_calls(units(db), actor.leads))
            call_scope = call_scope | Event.request_id.in_(calls)
        stmt = stmt.where(
            ~Event.action.startswith("profile."),
            (~invocation & business_scope) | (invocation & call_scope),
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
