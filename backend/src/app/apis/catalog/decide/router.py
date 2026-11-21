from app.apis.catalog.common import DB, NEXT, User, event, record, right_id
from app.apis.schemas import Decision, Right
from app.core.workspace import delegated
from app.db.models import Access
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.post(
    "/requests/{key}/{project}/{environment}/{principal}",
    response_model=Right,
    operation_id="decidePersonal",
)
@router.post("/requests/{key}/{project}/{environment}", response_model=Right, operation_id="decide")
def decide(
    key: str,
    project: str,
    environment: str,
    data: Decision,
    request: Request,
    actor: User,
    db: DB,
    principal: str = "",
):
    asset = record(db, key)
    row = db.get(Access, right_id(key, project, environment) + ("/" + principal if principal else ""))
    if row is None:
        raise HTTPException(404)
    if data.action == "withdraw":
        allowed = row.subject == actor.subject if row.subject else project in actor.projects
    else:
        allowed = asset.owner in actor.owners or (
            data.action in ("approve", "reject") and delegated(db, actor, asset, row)
        )
    if not allowed:
        raise HTTPException(403)
    previous, following = NEXT[data.action]
    if row.status != previous or row.revision != data.revision:
        raise HTTPException(409, "申請状態が変わりました。再読み込みしてください")
    row.status = following
    row.decision_note = data.reason
    event(db, request, actor, asset, data.action, project, environment, data.reason)
    db.commit()
    return row
