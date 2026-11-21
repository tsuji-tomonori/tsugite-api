import json

from app.apis.catalog.common import DB, User, listing, record
from app.apis.schemas import Detail
from app.core.workspace import allowed_audience
from app.db.models import Access
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

router = APIRouter()


@router.get("/apis/{key}", response_model=Detail, operation_id="detail")
def detail(key: str, actor: User, db: DB):
    a = record(db, key)
    grant = db.scalar(
        select(Access.id)
        .where(
            Access.asset_id == key,
            (
                (Access.subject.is_(None) & Access.project.in_(actor.projects))
                | (Access.subject == actor.subject)
            ),
            Access.status == "approved",
        )
        .limit(1)
    )
    if not allowed_audience(a, actor):
        raise HTTPException(404)
    if not a.published and a.owner not in actor.owners and not grant:
        raise HTTPException(404)
    return Detail(
        **listing(a).model_dump(),
        spec=json.loads(a.spec),
        base_path=a.base_path or "",
        bindings=json.loads(a.targets) if a.owner in actor.owners else {},
    )
