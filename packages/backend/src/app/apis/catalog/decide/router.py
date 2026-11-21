import json

from app.apis.catalog.common import DB, NEXT, User, event, record, right_id
from app.apis.catalog.offers import can_review
from app.apis.schemas import Decision, Right
from fastapi import APIRouter, HTTPException, Request
from tsugite_db.models import Access, now

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
    elif data.action == "revoke":
        allowed = asset.owner in actor.owners
    else:
        allowed = can_review(db, actor, asset, row)
    if not allowed:
        raise HTTPException(403)
    previous, following = NEXT[data.action]
    if row.status != previous or row.revision != data.revision:
        raise HTTPException(409, "申請状態が変わりました。再読み込みしてください")
    audit_action = data.action
    if row.stage and data.action in ("approve", "reject"):
        evidence = row.application
        evidence["decisions"].append(
            {
                "at": now().isoformat(),
                "stage": row.stage,
                "actor": actor.subject,
                "reason": data.reason,
                "action": data.action,
            }
        )
        next_index = len(evidence["decisions"])
        if data.action == "approve" and next_index < len(evidence["steps"]):
            row.stage = evidence["steps"][next_index]
            following = "pending"
            audit_action = "step.approve"
        else:
            row.stage = None
        row.submission = json.dumps(evidence, ensure_ascii=False)
    else:
        row.stage = None
    row.status = following
    row.decision_note = data.reason
    event(db, request, actor, asset, audit_action, project, environment, data.reason)
    db.commit()
    return row
