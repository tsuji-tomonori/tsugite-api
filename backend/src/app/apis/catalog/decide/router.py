from app.apis.catalog.common import DB, NEXT, User, event, record, right_id
from app.apis.schemas import Decision, Right
from app.db.models import Access
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.post("/requests/{key}/{project}/{environment}", response_model=Right, operation_id="decide")
def decide(
    key: str, project: str, environment: str, data: Decision, request: Request, actor: User, db: DB
):
    asset = record(db, key)
    allowed = project in actor.projects if data.action == "withdraw" else asset.owner in actor.owners
    if not allowed:
        raise HTTPException(403)
    row = db.get(Access, right_id(key, project, environment))
    if row is None:
        raise HTTPException(404)
    previous, following = NEXT[data.action]
    if row.status != previous or row.revision != data.revision:
        raise HTTPException(409, "申請状態が変わりました。再読み込みしてください")
    row.status = following
    event(db, request, actor, asset, data.action, project, environment, data.reason)
    db.commit()
    return row
